from dataclasses import dataclass
import json
import logging
import math
import time
from typing import Callable

from fastapi import Response
from limits import storage, strategies, RateLimitItemPerSecond


from aoai_simulated_api import constants
from aoai_simulated_api.models import RequestContext

logger = logging.getLogger(__name__)


@dataclass
class OpenAILimits:
    deployment: str
    tokens_per_minute: int
    limit_tokens_per_10s: RateLimitItemPerSecond
    limit_requests_per_10s: RateLimitItemPerSecond


def no_op_limiter(_: RequestContext, __: Response) -> None:
    return None


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

    def limiter(context: RequestContext, _: Response) -> Response | None:
        token_cost = context.values.get(constants.SIMULATOR_KEY_OPENAI_TOTAL_TOKENS)
        deployment_name = context.values.get(constants.SIMULATOR_KEY_DEPLOYMENT_NAME)

        if not token_cost or not deployment_name:
            logger.warning("openai_limiter: No token cost or deployment name found in context")

        limits = deployment_limits.get(deployment_name)
        if not limits:
            # TODO: log (only log once per deployment, not every call)
            return None

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
        return None

    return limiter


def create_doc_intelligence_limiter(
    limit_storage: storage.Storage, requests_per_second: int
) -> Callable[[RequestContext, Response], Response | None]:
    moving_window = strategies.MovingWindowRateLimiter(limit_storage)
    limit = RateLimitItemPerSecond(requests_per_second, 1)

    if requests_per_second <= 0:
        return no_op_limiter

    def limiter(_: RequestContext, __: Response) -> Response | None:
        if not moving_window.hit(limit):
            stats = moving_window.get_window_stats(limit)
            current_time = int(time.time())
            retry_after = str(stats.reset_time - current_time)
            content = {
                "error": {
                    "code": "429",
                    "message": "Requests to the Doc Intelligence API Simulator have exceeded call rate limit. "
                    + f"Please retry after {retry_after} seconds.",
                }
            }
            return Response(
                status_code=429,
                content=json.dumps(content),
                headers={"Retry-After": retry_after, "x-ratelimit-reset-requests": retry_after},
            )
        return None

    return limiter
