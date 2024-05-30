from dataclasses import dataclass
import json
import logging
import math
import time
from typing import Callable

from fastapi import Response
from limits import storage, strategies, RateLimitItemPerSecond


from aoai_simulated_api import constants
from aoai_simulated_api.models import Config, RequestContext

logger = logging.getLogger(__name__)


@dataclass
class OpenAILimits:
    deployment: str
    tokens_per_minute: int
    limit_tokens_per_10s: RateLimitItemPerSecond
    limit_requests_per_10s: RateLimitItemPerSecond


def apply_limits(context: RequestContext, response: Response) -> Response:
    limiter_name = context.values.get(constants.SIMULATOR_KEY_LIMITER)
    limiter = context.config.limiters.get(limiter_name) if limiter_name else None
    if limiter:
        limit_response = limiter(context, response)
        return limit_response

    logger.debug("No limiter found for response: %s", context.request.url.path)
    return response


def no_op_limiter(_: RequestContext, response: Response) -> None:
    return response


deployment_warnings_issues: dict[str, bool] = {}


def create_openai_limiter(
    limit_storage: storage.Storage, deployments: dict[str, int]
) -> Callable[[RequestContext, Response], Response | None]:
    deployment_limits = {}
    window = strategies.FixedWindowRateLimiter(limit_storage)

    for deployment, tokens_per_minute in deployments.items():
        tokens_per_10s = math.ceil(tokens_per_minute / 6)
        limit_tokens_per_10s = RateLimitItemPerSecond(tokens_per_10s, 10)

        # Logical breakdown:
        # requests_per_minute = (tokens_per_minute * 6) / 1000
        # requests_per_10s = math.ceil(requests_per_minute / 6)
        # i.e. requests_per_10s = math.ceil((tokens_per_minute * 6) / (1000 * 6))
        # which simplifies to
        requests_per_10s = math.ceil(tokens_per_minute / 1000)
        limit_requests_per_10s = RateLimitItemPerSecond(requests_per_10s, 10)

        deployment_limits[deployment] = OpenAILimits(
            deployment=deployment,
            tokens_per_minute=tokens_per_minute,
            limit_tokens_per_10s=limit_tokens_per_10s,
            limit_requests_per_10s=limit_requests_per_10s,
        )

    def limiter(context: RequestContext, response: Response) -> Response:
        token_cost = context.values.get(constants.SIMULATOR_KEY_OPENAI_TOTAL_TOKENS)
        deployment_name = context.values.get(constants.SIMULATOR_KEY_DEPLOYMENT_NAME)

        if not token_cost or not deployment_name:
            logger.warning("openai_limiter: No token cost or deployment name found in context")

        limits = deployment_limits.get(deployment_name)
        if not limits:
            if not deployment_warnings_issues.get(deployment_name):
                logger.warning("Deployment %s not found in limiters - not applying rate limits", deployment_name)
                deployment_warnings_issues[deployment_name] = True
            return response

        # TODO: revisit limiting logic: also track per minute limits? Allow burst?

        if not window.hit(limits.limit_requests_per_10s):
            stats = window.get_window_stats(limit_requests_per_10s)
            current_time = int(time.time())
            retry_after = str(stats.reset_time - current_time)
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
                headers={"Retry-After": retry_after, "x-ratelimit-reset-requests": retry_after},
            )
        if not window.hit(limits.limit_tokens_per_10s, cost=token_cost):
            stats = window.get_window_stats(limit_tokens_per_10s)
            current_time = int(time.time())
            retry_after = str(stats.reset_time - current_time)
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
                headers={"Retry-After": retry_after, "x-ratelimit-reset-requests": retry_after},
            )
        return response

    return limiter


def get_default_limiters(config: Config):
    openai_deployment_limits = (
        {name: deployment.tokens_per_minute for name, deployment in config.openai_deployments.items()}
        if config.openai_deployments
        else {}
    )

    memory_storage = storage.MemoryStorage()
    # Dictionary of limiters keyed by name
    # Each limiter is a function that takes a response and returns a boolean indicating
    # whether the request should be allowed
    # Limiter returns Response object if request should be blocked or None otherwise
    return {
        "openai": create_openai_limiter(memory_storage, openai_deployment_limits),
    }
