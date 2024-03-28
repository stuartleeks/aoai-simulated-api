import asyncio
import logging
import os
import traceback
from typing import Callable
from fastapi import FastAPI, Request, Response
from limits import storage

import aoai_simulated_api.constants as constants
from aoai_simulated_api.config import Config, load_doc_intelligence_limit
from aoai_simulated_api.generator import GeneratorManager
from aoai_simulated_api.limiters import create_openai_limiter, create_doc_intelligence_limiter
from aoai_simulated_api.pipeline import RequestContext
from aoai_simulated_api.record_replay import (
    RecordReplayHandler,
    YamlRecordingPersister,
    RequestForwarder,
)


def get_simulator(logger: logging.Logger, config: Config) -> FastAPI:
    """
    Create the FastAPI app for the simulator based on provided configuration
    """
    app = FastAPI()

    logger.info("🚀 Starting aoai-simulated-api in %s mode", config.simulator_mode)
    module_path = os.path.dirname(os.path.realpath(__file__))
    if config.simulator_mode == "generate":
        logger.info("📝 Generator config path: %s", config.generator_config_path)
        generator_config_path = config.generator_config_path or os.path.join(module_path, "generator/default_config.py")

        generator_manager = GeneratorManager(generator_config_path=generator_config_path)
    else:
        logger.info("📼 Recording directory      : %s", config.recording.dir)
        logger.info("📼 Recording format         : %s", config.recording.format)
        logger.info("📼 Recording auto-save      : %s", config.recording.autosave)
        # TODO - handle JSON loading (or update docs!)
        if config.recording.format != "yaml":
            raise ValueError(f"Unsupported recording format: {config.recording.format}")
        persister = YamlRecordingPersister(config.recording.dir)

        forwarder = None
        forwarder_config_path = config.recording.forwarder_config_path or os.path.join(
            module_path, "record_replay/_request_forwarder_config.py"
        )
        if config.simulator_mode == "record":
            logger.info("📼 Forwarder config path: %s", forwarder_config_path)
            forwarder = RequestForwarder(forwarder_config_path)

        record_replay_handler = RecordReplayHandler(
            simulator_mode=config.simulator_mode,
            persister=persister,
            forwarder=forwarder,
            autosave=config.recording.autosave,
        )

    @app.get("/")
    async def root():
        return {"message": "👋 aoai-simulated-api is running"}

    @app.post("/++/save-recordings")
    def save_recordings():
        if config.simulator_mode == "record":
            logger.info("📼 Saving recordings...")
            record_replay_handler.save_recordings()
            logger.info("📼 Recordings saved")
            return Response(content="📼 Recordings saved", status_code=200)
        else:
            logger.warn("⚠️ Not saving recordings as not in record mode")
            return Response(content="⚠️ Not saving recordings as not in record mode", status_code=400)

    memory_storage = storage.MemoryStorage()

    doc_intelligence_rps = load_doc_intelligence_limit()
    logger.info("📝 Using Doc Intelligence RPS: %s", doc_intelligence_rps)

    logger.info("📝 Using OpenAI deployments: %s", config.openai_deployments)

    openai_deployment_limits = (
        {name: deployment.tokens_per_minute for name, deployment in config.openai_deployments.items()}
        if config.openai_deployments
        else {}
    )
    # Dictionary of limiters keyed by name
    # Each limiter is a function that takes a response and returns a boolean indicating
    # whether the request should be allowed
    # Limiter returns Response object if request should be blocked or None otherwise
    limiters: dict[str, Callable[[Response], Response | None]] = {
        "openai": create_openai_limiter(memory_storage, openai_deployment_limits),
        "docintelligence": create_doc_intelligence_limiter(memory_storage, requests_per_second=doc_intelligence_rps),
    }

    @app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE"])
    async def catchall(request: Request):
        logger.debug("⚡ handling route: %s", request.url.path)

        try:
            response = None
            context = RequestContext(config=config, request=request)

            if config.simulator_mode == "generate":
                response = await generator_manager.generate(context)

            if config.simulator_mode in ["record", "replay"]:
                response = await record_replay_handler.handle_request(context)

            if not response:
                logger.error("No response generated for request: %s", request.url.path)
                return Response(status_code=500)

            # Want limits here so that that they apply to record/replay as well as generate
            # TODO work out mapping request to limiter(s)
            #  - AOAI specifies rate limits by deployment and uses RPM + TPM
            #  - Doc Intelligence uses flat RPM limit

            limiter_name = response.headers.get(constants.SIMULATOR_HEADER_LIMITER)
            limiter = limiters.get(limiter_name) if limiter_name else None
            if limiter:
                limit_response = limiter(response)
                if limit_response:
                    return limit_response
            else:
                logger.debug("No limiter found for response: %s", request.url.path)

            recorded_duration_ms = context.values.get(constants.RECORDED_DURATION_MS, 0)
            if recorded_duration_ms > 0:
                await asyncio.sleep(recorded_duration_ms / 1000)

            # Strip out any simulator headers from the response
            # TODO - move these header values to RequestContext to share
            #        (then they don't need removing here!)
            for key, _ in request.headers.items():
                if key.startswith(constants.SIMULATOR_HEADER_PREFIX):
                    del response.headers[key]

            return response
        # pylint: disable-next=broad-exception-caught
        except Exception as e:
            logger.error("Error: %s\n%s", e, traceback.format_exc())
            return Response(status_code=500)

    return app
