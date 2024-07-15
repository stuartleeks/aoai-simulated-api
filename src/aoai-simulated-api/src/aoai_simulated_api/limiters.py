from dataclasses import dataclass
import inspect
import json
import logging
import math
import os
import time
from string import Template
from typing import Awaitable, Callable

from fastapi import Response

from aoai_simulated_api import constants
from aoai_simulated_api.metrics import simulator_metrics
from aoai_simulated_api.models import Config, RequestContext

logger = logging.getLogger(__name__)


@dataclass
class OpenAILimits:
    """
    OpenAILimits stores the rate limits for a given deployment.
    This uses a token-bucket rate limiter to enforce rate limits.
    Unfortunately, the terms token conflicts between the rate-limiter and
    OpenAI tokens.
    """

    deployment: str
    # The number of AOAI tokens per minute is the max size of the token bucket for AOAI tokens
    openai_tokens_per_minute: int
    # The number of AOAI tokens per second is the bucket refresh rate for AOAI tokens
    openai_tokens_per_second: float
    openai_tokens_available: int
    openai_tokens_last_refresh: float

    # The number of requests per 10 seconds is the max size of the token bucket for requests
    openai_requests_per_10_seconds: float
    # The number of requests per second is the bucket refresh rate for requests
    openai_requests_per_second: float
    openai_requests_available: float
    openai_requests_last_refresh: float


async def apply_limits(context: RequestContext, response: Response) -> Awaitable[Response]:
    limiter_name = context.values.get(constants.SIMULATOR_KEY_LIMITER)
    limiter = context.config.limiters.get(limiter_name) if limiter_name else None
    if limiter:
        limit_response = limiter(context, response)
        if limit_response and inspect.isawaitable(limit_response):
            limit_response = await limit_response
        return limit_response

    logger.info("No limiter found for response: %s [limiter name: %s]", context.request.url.path, limiter_name)
    return response


def no_op_limiter(_: RequestContext, response: Response) -> None:
    return response


deployment_warnings_issues: dict[str, bool] = {}


async def determine_token_cost(context: RequestContext):
    # Check whether the request has set max_tokens
    # If so, use that as the rate-limiting token value
    request_body = await context.request.json()
    max_tokens = request_body.get("max_tokens")
    if max_tokens:
        token_cost = max_tokens
    else:
        # otherwise, calculate the rate-limiting token cost
        if "/chat/completions" in context.request.url.path:
            token_cost = 16
        elif "/embeddings" in context.request.url.path:
            request_body = await context.request.json()
            request_input = request_body.get("input")
            if request_input is None:
                logger.warning("openai_limiter: input not found in request body for embedding request")
                token_cost = 0
            else:
                if isinstance(request_input, list):
                    # TODO - validate whether we should sum the ceil values or ceil the sum
                    token_cost = sum([math.ceil(len(input_str) / 4) for input_str in request_input])
                else:
                    token_cost = math.ceil(len(request_input) / 4)
        else:
            # TODO: implement calculations for other endpoints
            logger.warning("openai_limiter: unhanndled endpoint %s", context.request.url.path)
            token_cost = 0

    logger.info("openai_limiter: token cost for %s is %d", context.request.url.path, token_cost)
    context.values[constants.SIMULATOR_KEY_OPENAI_RATE_LIMIT_TOKENS] = token_cost  # TODO add a metric for this?
    return token_cost


def create_openai_limiter(deployments: dict[str, int]) -> Callable[[RequestContext, Response], Response | None]:
    deployment_limits: dict[str, OpenAILimits] = {}

    for deployment, tokens_per_minute in deployments.items():
        # Logical breakdown:
        # 1k tokens per minute => 6 requests per minute
        # requests_per_minute = (tokens_per_minute * 6) / 1000
        # requests_per_10s = math.ceil(requests_per_minute / 6)
        # i.e. requests_per_10s = math.ceil((tokens_per_minute * 6) / (1000 * 6))
        # which simplifies to
        requests_per_10s = math.ceil(tokens_per_minute / 1000)

        now = time.time()
        deployment_limits[deployment] = OpenAILimits(
            deployment=deployment,
            openai_tokens_per_minute=tokens_per_minute,
            openai_tokens_per_second=tokens_per_minute / 60.0,
            openai_tokens_available=tokens_per_minute,
            openai_tokens_last_refresh=now,
            openai_requests_per_10_seconds=requests_per_10s,
            openai_requests_per_second=requests_per_10s / 10.0,
            openai_requests_available=requests_per_10s,
            openai_requests_last_refresh=now,
        )

    async def limiter(context: RequestContext, response: Response) -> Awaitable[Response]:
        deployment_name = context.values.get(constants.SIMULATOR_KEY_DEPLOYMENT_NAME)

        token_cost = await determine_token_cost(context)
        if not deployment_name:
            logger.warning("openai_limiter: deployment name found in context")

        limits = deployment_limits.get(deployment_name)
        if not limits:
            if not deployment_warnings_issues.get(deployment_name):
                logger.warning("Deployment %s not found in limiters - not applying rate limits", deployment_name)
                deployment_warnings_issues[deployment_name] = True
            return response

        # Refresh buckets
        now = time.time()
        tokens_time_passed = now - limits.openai_tokens_last_refresh
        tokens_to_add = tokens_time_passed * limits.openai_tokens_per_second
        limits.openai_tokens_available = min(
            limits.openai_tokens_available + tokens_to_add, limits.openai_tokens_per_minute
        )
        limits.openai_tokens_last_refresh = now

        requests_time_passed = now - limits.openai_requests_last_refresh
        requests_to_add = requests_time_passed * limits.openai_requests_per_second
        limits.openai_requests_available = min(
            limits.openai_requests_available + requests_to_add, limits.openai_requests_per_10_seconds
        )
        limits.openai_requests_last_refresh = now

        if limits.openai_tokens_available < token_cost or limits.openai_requests_available < 1:
            # Insufficient capacity in at least one bucket

            if limits.openai_tokens_available < token_cost:
                time_to_reset_tokens = (token_cost - limits.openai_tokens_available) / limits.openai_tokens_per_second
            else:
                time_to_reset_tokens = 0

            if limits.openai_requests_available < 1:
                time_to_reset_requests = (1 - limits.openai_requests_available) / limits.openai_requests_per_second
            else:
                time_to_reset_requests = 0

            if time_to_reset_tokens > time_to_reset_requests:
                cost = token_cost
                reason = "tokens"
                retry_after = str(math.ceil(time_to_reset_tokens))
                retry_after_header = "x-ratelimit-reset-tokens"
            else:
                cost = 1
                reason = "requests"
                retry_after = str(math.ceil(time_to_reset_requests))
                retry_after_header = "x-ratelimit-reset-requests"

            simulator_metrics.histogram_rate_limit.record(
                cost,
                attributes={
                    "deployment": deployment_name,
                    "reason": reason,
                },
            )

            content = {
                "error": {
                    "code": "429",
                    "message": "Requests to the OpenAI API Simulator have exceeded call rate limit. "
                    + f"Please retry after {retry_after} seconds.",
                }
            }
            return Response(
                status_code=429,
                content=json.dumps(content),
                headers={"Retry-After": retry_after, retry_after_header: retry_after},
            )

        # Consume from buckets
        limits.openai_tokens_available -= token_cost
        limits.openai_requests_available -= 1

        # Add rate limit headers to response
        logger.info(
            "openai_limiter: tokens available: %d\t requests available: %d",
            limits.openai_tokens_available,
            limits.openai_requests_available,
        )
        response.headers["x-ratelimit-remaining-tokens"] = str(math.floor(limits.openai_tokens_available))
        response.headers["x-ratelimit-remaining-requests"] = str(math.floor(limits.openai_requests_available))

        return response

    return limiter


def get_default_limiters(config: Config):
    openai_deployment_limits = (
        {name: deployment.tokens_per_minute for name, deployment in config.openai_deployments.items()}
        if config.openai_deployments
        else {}
    )

    # Dictionary of limiters keyed by name
    # Each limiter is a function that takes a response and returns a boolean indicating
    # whether the request should be allowed
    # Limiter returns Response object if request should be blocked or None otherwise
    return {
        "openai": create_openai_limiter(openai_deployment_limits),
    }
