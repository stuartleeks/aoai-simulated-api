import asyncio
from dataclasses import dataclass
import time
from fastapi import Response
from opentelemetry import trace, metrics

from aoai_simulated_api import constants
from aoai_simulated_api.models import RequestContext


@dataclass
class SimulatorMetrics:
    histogram_latency_base: metrics.Histogram
    histogram_latency_full: metrics.Histogram
    histogram_tokens_used: metrics.Histogram
    histogram_tokens_requested: metrics.Histogram


def _get_simulator_metrics() -> SimulatorMetrics:
    meter = metrics.get_meter(__name__)
    return SimulatorMetrics(
        histogram_latency_base=meter.create_histogram(
            name="aoai-simulator.latency.base",
            description="Latency of handling the request (before adding simulated latency)",
            unit="seconds",
        ),
        histogram_latency_full=meter.create_histogram(
            name="aoai-simulator.latency.full",
            description="Full latency of handling the request (including simulated latency)",
            unit="seconds",
        ),
        histogram_tokens_used=meter.create_histogram(
            name="aoai-simulator.tokens_used",
            description="Number of tokens used per request",
            unit="tokens",
        ),
        histogram_tokens_requested=meter.create_histogram(
            name="aoai-simulator.tokens_requested",
            description="Number of tokens across all requests (success or not)",
            unit="tokens",
        ),
    )


simulator_metrics = _get_simulator_metrics()


class LatencyGenerator:
    """
    LatencyGenerator is a context manager that adds simulated latency to the response.
    The latency added is based on the context.values[TARGET_DURATION_MS] value.
    Additionaly, the generator emits metrics for the response (base latency and added latency).
    """

    __context: RequestContext
    __start_time: float
    __response: Response | None

    def __init__(self, context: RequestContext):
        self.__context = context
        self.__response = None

    def set_response(self, response: Response):
        self.__response = response

    async def __aenter__(self):
        self.__start_time = time.perf_counter()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.apply_latency()

    async def apply_latency(self):
        """Apply additional latency to the request if required"""

        # Only adding latency to succesful responses
        if not self.__response:
            return

        status_code = self.__response.status_code
        if status_code >= 300:
            return

        base_end_time = time.perf_counter()
        base_duration_s = base_end_time - self.__start_time

        deployment_name = self.__context.values.get(constants.SIMULATOR_KEY_DEPLOYMENT_NAME)
        tokens_used = self.__context.values.get(constants.SIMULATOR_KEY_OPENAI_TOTAL_TOKENS)

        target_duration_ms = self.__context.values.get(constants.TARGET_DURATION_MS, None)
        if not target_duration_ms:
            return

        target_duration_s = target_duration_ms / 1000
        extra_latency_s = target_duration_s - base_duration_s

        if extra_latency_s and extra_latency_s > 0:
            current_span = trace.get_current_span()
            current_span.set_attribute("simulator.added_latency", extra_latency_s)
            await asyncio.sleep(extra_latency_s)

        full_end_time = time.perf_counter()
        simulator_metrics.histogram_latency_base.record(
            base_duration_s,
            attributes={
                "status_code": status_code,
                "deployment": deployment_name,
            },
        )
        simulator_metrics.histogram_latency_full.record(
            (full_end_time - self.__start_time),
            attributes={
                "status_code": status_code,
                "deployment": deployment_name,
            },
        )
        if tokens_used:
            simulator_metrics.histogram_tokens_requested.record(tokens_used, attributes={"deployment": deployment_name})
            if status_code < 300:
                # only track tokens for successful requests
                simulator_metrics.histogram_tokens_used.record(tokens_used, attributes={"deployment": deployment_name})
