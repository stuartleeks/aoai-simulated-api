import asyncio
from dataclasses import dataclass
import logging
import time
import traceback
from typing import Annotated, Callable
from fastapi import Depends, FastAPI, Request, Response, HTTPException
from limits import storage
from opentelemetry import trace, metrics

from aoai_simulated_api import constants
from aoai_simulated_api.auth import validate_api_key_header
from aoai_simulated_api.config_loader import get_config, set_config
from aoai_simulated_api.generator.manager import invoke_generators
from aoai_simulated_api.limiters import create_openai_limiter, create_doc_intelligence_limiter
from aoai_simulated_api.models import RequestContext
from aoai_simulated_api.record_replay.handler import RecordReplayHandler
from aoai_simulated_api.record_replay.persistence import YamlRecordingPersister


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


logger = logging.getLogger(__name__)

app = FastAPI()


simulator_metrics = _get_simulator_metrics()

# pylint: disable-next=invalid-name
record_replay_handler = None
limiters: dict[str, Callable[[RequestContext, Response], Response | None]] = {}


def initialize():
    # pylint: disable-next=global-statement
    global record_replay_handler, limiters

    record_replay_handler = None
    limiters = {}

    logger.info("🚀 Starting aoai-simulated-api in %s mode", get_config().simulator_mode)
    logger.info("🗝️ Simulator api-key        : %s", get_config().simulator_api_key)

    if get_config().simulator_mode in ["record", "replay"]:
        logger.info("📼 Recording directory      : %s", get_config().recording.dir)
        logger.info("📼 Recording auto-save      : %s", get_config().recording.autosave)
        persister = YamlRecordingPersister(get_config().recording.dir)

        record_replay_handler = RecordReplayHandler(
            simulator_mode=get_config().simulator_mode,
            persister=persister,
            forwarders=get_config().recording.forwarders,
            autosave=get_config().recording.autosave,
        )

    logger.info("📝 Using OpenAI deployments: %s", get_config().openai_deployments)

    openai_deployment_limits = (
        {name: deployment.tokens_per_minute for name, deployment in get_config().openai_deployments.items()}
        if get_config().openai_deployments
        else {}
    )

    memory_storage = storage.MemoryStorage()
    # Dictionary of limiters keyed by name
    # Each limiter is a function that takes a response and returns a boolean indicating
    # whether the request should be allowed
    # Limiter returns Response object if request should be blocked or None otherwise
    limiters = {
        "openai": create_openai_limiter(memory_storage, openai_deployment_limits),
        # "docintelligence": create_doc_intelligence_limiter(
        #     memory_storage, requests_per_second=get_config().doc_intelligence_rps
        # ),
    }


def _default_validate_api_key_header(request: Request):
    validate_api_key_header(request=request, header_name="api-key", allowed_key_value=get_config().simulator_api_key)


@app.get("/")
async def root():
    return {"message": "👋 aoai-simulated-api is running"}


@app.post("/++/save-recordings")
def save_recordings(_: Annotated[bool, Depends(_default_validate_api_key_header)]):
    if get_config().simulator_mode == "record":
        logger.info("📼 Saving recordings...")
        record_replay_handler.save_recordings()
        logger.info("📼 Recordings saved")
        return Response(content="📼 Recordings saved", status_code=200)

    logger.warning("⚠️ Not saving recordings as not in record mode")
    return Response(content="⚠️ Not saving recordings as not in record mode", status_code=400)


@app.get("/++/config")
def config_get(_: Annotated[bool, Depends(_default_validate_api_key_header)]):
    # return a subset of the config as not all properties make sense (e.g. generator functions)
    config = get_config()
    return {
        "simulator_mode": config.simulator_mode,
        "latency": {
            "open_ai_embeddings": {
                "mean": config.latency.open_ai_embeddings.mean,
                "std_dev": config.latency.open_ai_embeddings.std_dev,
            },
            "open_ai_completions": {
                "mean": config.latency.open_ai_completions.mean,
                "std_dev": config.latency.open_ai_completions.std_dev,
            },
            "open_ai_chat_completions": {
                "mean": config.latency.open_ai_chat_completions.mean,
                "std_dev": config.latency.open_ai_chat_completions.std_dev,
            },
        },
        "openai_deployments": (
            {
                name: {"tokens_per_minute": deployment.tokens_per_minute, "model": deployment.model}
                for name, deployment in config.openai_deployments.items()
            }
            if config.openai_deployments
            else None
        ),
    }


@app.patch("/++/config")
def config_patch(config: dict, _: Annotated[bool, Depends(_default_validate_api_key_header)]):
    original_config = get_config()

    # Config is a nested settings class to enable setting env var names on child items
    # As a result we need to update each level independently
    root_dict = {k: v for k, v in config.items() if k in ["simulator_mode"]}
    new_config = original_config.model_copy(update=root_dict)
    if "latency" in config:
        if "open_ai_completions" in config["latency"]:
            new_config.latency.open_ai_completions = original_config.latency.open_ai_completions.model_copy(
                update=config["latency"]["open_ai_completions"]
            )
        if "open_ai_chat_completions" in config["latency"]:
            new_config.latency.open_ai_chat_completions = original_config.latency.open_ai_chat_completions.model_copy(
                update=config["latency"]["open_ai_chat_completions"]
            )
        if "open_ai_embeddings" in config["latency"]:
            new_config.latency.open_ai_embeddings = original_config.latency.open_ai_embeddings.model_copy(
                update=config["latency"]["open_ai_embeddings"]
            )

    # Update the config and re-initialize
    set_config(new_config)
    initialize()

    return config_get(_)


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def catchall(request: Request):
    logger.debug("⚡ handling route: %s", request.url.path)
    # TODO check for traceparent in inbound request and propagate
    #      to allow for correlating load test with back-end data

    start_time = time.perf_counter()  # N.B. this doesn't accound for the validate_api_key time

    try:
        response = None
        context = RequestContext(config=get_config(), request=request)

        # Get response
        if get_config().simulator_mode == "generate":
            response = await invoke_generators(context, get_config().generators)
        elif get_config().simulator_mode in ["record", "replay"]:
            response = await record_replay_handler.handle_request(context)

        if not response:
            logger.error("No response found for request: %s", request.url.path)
            return Response(status_code=500)

        # Apply limits here so that that they apply to record/replay as well as generate
        response = apply_limits(context, response)

        # Add latency to successful responses
        base_end_time = time.perf_counter()
        base_duration_s = base_end_time - start_time

        status_code = response.status_code
        deployment_name = context.values.get(constants.SIMULATOR_KEY_DEPLOYMENT_NAME)
        tokens_used = context.values.get(constants.SIMULATOR_KEY_OPENAI_TOTAL_TOKENS)
        completion_tokens = context.values.get(constants.SIMULATOR_KEY_OPENAI_COMPLETION_TOKENS)
        await apply_latency(context, base_duration_s, status_code, tokens_used, completion_tokens)

        full_end_time = time.perf_counter()
        simulator_metrics.histogram_latency_base.record(
            base_duration_s,
            attributes={
                "status_code": status_code,
                "deployment": deployment_name,
            },
        )
        simulator_metrics.histogram_latency_full.record(
            (full_end_time - start_time),
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

        return response
    except HTTPException as he:
        raise he
    # pylint: disable-next=broad-exception-caught
    except Exception as e:
        logger.error("Error: %s\n%s", e, traceback.format_exc())
        return Response(status_code=500)


def apply_limits(context: RequestContext, response: Response) -> Response:
    limiter_name = context.values.get(constants.SIMULATOR_KEY_LIMITER)
    limiter = limiters.get(limiter_name) if limiter_name else None
    if limiter:
        limit_response = limiter(context, response)
        if limit_response:
            # replace response with limited response
            response = limit_response
    else:
        logger.debug("No limiter found for response: %s", context.request.url.path)
    return response


async def apply_latency(context, base_duration_s, status_code, tokens_used, completion_tokens):
    if status_code < 300:
        # Determine if we need to add extra latency to simulate the time it took to generate the response
        # TODO - enable config and extensibility to control this (consider splitting calculation from application and telemetry)
        extra_latency_s = None
        recorded_duration_ms = context.values.get(constants.RECORDED_DURATION_MS, None)
        if recorded_duration_ms:
            recorded_duration_s = recorded_duration_ms / 1000
            extra_latency_s = recorded_duration_s - base_duration_s
        elif tokens_used and tokens_used > 0:
            operation_name = context.values.get(constants.SIMULATOR_KEY_OPERATION_NAME)
            if operation_name == "embeddings":
                # embeddings config returns latency value to use (in milliseconds)
                extra_latency_s = get_config().latency.open_ai_embeddings.get_value() / 1000
            elif operation_name == "completions":
                # completions config returns latency per completion token in milliseconds
                ms_per_token = get_config().latency.open_ai_completions.get_value()
                extra_latency_s = ms_per_token * completion_tokens / 1000
            elif operation_name == "chat-completions":
                # chat completions config returns latency per completion token in milliseconds
                ms_per_token = get_config().latency.open_ai_chat_completions.get_value()
                extra_latency_s = ms_per_token * completion_tokens / 1000

        if extra_latency_s and extra_latency_s > 0:
            current_span = trace.get_current_span()
            current_span.set_attribute("simulator.added_latency", extra_latency_s)
            await asyncio.sleep(extra_latency_s)
