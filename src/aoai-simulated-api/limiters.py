from dataclasses import dataclass
import json
import math
import time
from typing import Callable

from fastapi import Response
from limits import storage, strategies, RateLimitItemPerSecond


import constants


@dataclass
class OpenAILimits:
    deployment: str
    tokens_per_minute: int
    limit_tokens_per_10s: RateLimitItemPerSecond
    limit_requests_per_10s: RateLimitItemPerSecond


def create_openai_limiter(
    storage: storage.Storage, deployments: dict[str, int]
) -> Callable[[Response], Response | None]:
    moving_window = strategies.MovingWindowRateLimiter(storage)
    deployment_limits = {}

    for deployment, tokens_per_minute in deployments.items():
        tokens_per_10s = math.ceil(tokens_per_minute / 6)
        limit_tokens_per_10s = RateLimitItemPerSecond(tokens_per_10s, 10)

        requests_per_10s = math.ceil(tokens_per_minute / (1000 * 6))
        limit_requests_per_10s = RateLimitItemPerSecond(requests_per_10s, 10)

        deployment_limits[deployment] = OpenAILimits(
            deployment=deployment,
            tokens_per_minute=tokens_per_minute,
            limit_tokens_per_10s=limit_tokens_per_10s,
            limit_requests_per_10s=limit_requests_per_10s,
        )

    def limiter(response: Response) -> Response | None:
        # TODO - handle header not present
        token_cost = int(response.headers[constants.SIMULATOR_HEADER_OPENAI_TOKENS])
        deployment_name = response.headers[constants.SIMULATOR_HEADER_LIMITER_KEY]

        limits = deployment_limits.get(deployment_name)
        if not limits:
            # TODO: log
            return None

        # TODO: revisit limiting logic: also track per minute limits? Allow burst?

        # TODO: add logging on rate limiting
        if not moving_window.hit(limits.limit_requests_per_10s):
            stats = moving_window.get_window_stats(limit_requests_per_10s)
            current_time = int(time.time())
            retry_after = str(stats.reset_time - current_time)
            content = {
                "error": {
                    "code": "429",
                    "message": f"Requests to the OpenAI API Simulator have exceeded call rate limit. Please retry after {retry_after} seconds.",
                }
            }
            return Response(
                status_code=429,
                content=json.dumps(content),
                headers={"Retry-After": retry_after, "x-ratelimit-reset-requests": retry_after},
            )
        if not moving_window.hit(limits.limit_tokens_per_10s, cost=token_cost):
            stats = moving_window.get_window_stats(limit_tokens_per_10s)
            current_time = int(time.time())
            retry_after = str(stats.reset_time - current_time)
            content = {
                "error": {
                    "code": "429",
                    "message": f"Requests to the OpenAI API Simulator have exceeded call rate limit. Please retry after {retry_after} seconds.",
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
    storage: storage.Storage, requests_per_second: int
) -> Callable[[Response], Response | None]:
    moving_window = strategies.MovingWindowRateLimiter(storage)
    limit = RateLimitItemPerSecond(requests_per_second, 1)

    def limiter(response: Response) -> Response | None:
        # TODO: add logging on rate limiting
        if not moving_window.hit(limit):
            stats = moving_window.get_window_stats(limit)
            current_time = int(time.time())
            retry_after = str(stats.reset_time - current_time)
            content = {
                "error": {
                    "code": "429",
                    "message": f"Requests to the Doc Intelligence API Simulator have exceeded call rate limit. Please retry after {retry_after} seconds.",
                }
            }
            return Response(
                status_code=429,
                content=json.dumps(content),
                headers={"Retry-After": retry_after, "x-ratelimit-reset-requests": retry_after},
            )
        return None

    return limiter
