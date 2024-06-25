from dataclasses import dataclass
import json
import logging
import math
import time
from typing import Callable

from fastapi import Response
from limits import RateLimitItem, storage, strategies, RateLimitItemPerSecond


from aoai_simulated_api import constants
from aoai_simulated_api.metrics import simulator_metrics
from aoai_simulated_api.models import Config, RequestContext

logger = logging.getLogger(__name__)


@dataclass
class RateLimitItemWithName:
    name: str
    limiter: RateLimitItem
    token_limit: bool


@dataclass
class OpenAILimits:
    deployment: str
    tokens_per_minute: int
    limit_tokens_per_10s: RateLimitItemPerSecond
    limit_requests_per_10s: RateLimitItemPerSecond
    limit_tokens_per_minute: RateLimitItemPerSecond
    limit_requests_per_minute: RateLimitItemPerSecond
    limiters: list[RateLimitItemWithName]


def apply_limits(context: RequestContext, response: Response) -> Response:
    limiter_name = context.values.get(constants.SIMULATOR_KEY_LIMITER)
    limiter = context.config.limiters.get(limiter_name) if limiter_name else None
    if limiter:
        limit_response = limiter(context, response)
        return limit_response

    logger.info("No limiter found for response: %s [limiter name: %s]", context.request.url.path, limiter_name)
    return response


def no_op_limiter(_: RequestContext, response: Response) -> None:
    return response


deployment_warnings_issues: dict[str, bool] = {}


def create_openai_limiter(
    limit_storage: storage.Storage, deployments: dict[str, int]
) -> Callable[[RequestContext, Response], Response | None]:
    deployment_limits: dict[str, OpenAILimits] = {}
    window = strategies.FixedWindowRateLimiter(limit_storage)

    for deployment, tokens_per_minute in deployments.items():
        tokens_per_10s = math.ceil(tokens_per_minute / 6)
        limit_tokens_per_10s = RateLimitItemPerSecond(tokens_per_10s, 10)
        limit_tokens_per_minute = RateLimitItemPerSecond(tokens_per_minute, 60)

        # Logical breakdown:
        # 1k tokens per minute => 6 requests per minute
        # requests_per_minute = (tokens_per_minute * 6) / 1000
        # requests_per_10s = math.ceil(requests_per_minute / 6)
        # i.e. requests_per_10s = math.ceil((tokens_per_minute * 6) / (1000 * 6))
        # which simplifies to
        requests_per_10s = math.ceil(tokens_per_minute / 1000)
        limit_requests_per_10s = RateLimitItemPerSecond(requests_per_10s, 10)
        requests_per_minute = math.ceil(tokens_per_minute * 6 / 1000)
        limit_requests_per_minute = RateLimitItemPerSecond(requests_per_minute, 60)

        deployment_limits[deployment] = OpenAILimits(
            deployment=deployment,
            tokens_per_minute=tokens_per_minute,
            limit_tokens_per_10s=limit_tokens_per_10s,
            limit_requests_per_10s=limit_requests_per_10s,
            limit_tokens_per_minute=limit_tokens_per_minute,
            limit_requests_per_minute=limit_requests_per_minute,
            limiters=[
                RateLimitItemWithName("tokens_per_10s", limit_tokens_per_10s, token_limit=True),
                RateLimitItemWithName("requests_per_10s", limit_requests_per_10s, token_limit=False),
                RateLimitItemWithName("tokens_per_minute", limit_tokens_per_minute, token_limit=True),
                RateLimitItemWithName("requests_per_minute", limit_requests_per_minute, token_limit=False),
            ],
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

        # Apply limits in turn to determine if the request should be allowed through
        for limit in limits.limiters:
            cost = token_cost if limit.token_limit else 1
            if not window.hit(limit.limiter, cost=cost):
                stats = window.get_window_stats(limit.limiter)
                current_time = int(time.time())
                retry_after = str(stats.reset_time - current_time)
                content = {
                    "error": {
                        "code": "429",
                        "message": "Requests to the OpenAI API Simulator have exceeded call rate limit. "
                        + f"Please retry after {retry_after} seconds.",
                    }
                }
                simulator_metrics.histogram_rate_limit.record(
                    cost,
                    attributes={
                        "deployment": deployment_name,
                        "reason": limit.name,
                    },
                )
                return Response(
                    status_code=429,
                    content=json.dumps(content),
                    headers={"Retry-After": retry_after, "x-ratelimit-reset-requests": retry_after},
                )

        # Add rate limit headers to response
        tpm_stats = window.get_window_stats(limits.limit_tokens_per_minute)
        rpm_stats = window.get_window_stats(limits.limit_requests_per_minute)
        response.headers["x-ratelimit-remaining-tokens"] = str(tpm_stats.remaining)
        response.headers["x-ratelimit-remaining-requests"] = str(rpm_stats.remaining)

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
