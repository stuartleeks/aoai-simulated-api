import asyncio
from dataclasses import dataclass
import logging
import os
import traceback
from typing import Callable
from fastapi import FastAPI, Request, Response
from limits import storage

import aoai_simulated_api.constants as constants
from aoai_simulated_api.config import load_openai_deployments, load_doc_intelligence_limit
from aoai_simulated_api.generator import GeneratorManager
from aoai_simulated_api.limiters import create_openai_limiter, create_doc_intelligence_limiter
from aoai_simulated_api.pipeline import RequestContext
from aoai_simulated_api.record_replay import (
    RecordReplayHandler,
    YamlRecordingPersister,
    RequestForwarder,
)


@dataclass
class Config:
    """
    Configuration for the simulator
    """

    # TODO: move into config.py
    # TODO: restructure, e.g. group recording settings together
    # TODO: combine OpenAI deployment configuration
    simulator_mode: str
    recording_dir: str
    recording_format: str
    recording_autosave: bool
    generator_config_path: str | None
    forwarder_config_path: str | None
    recording_format: str


def get_config_from_env_vars(logger: logging.Logger) -> Config:
    """
    Load configuration from environment variables
    """
    simulator_mode = os.getenv("SIMULATOR_MODE") or "replay"
    recording_dir = os.getenv("RECORDING_DIR") or ".recording"
    recording_dir = os.path.abspath(recording_dir)
    recording_format = os.getenv("RECORDING_FORMAT") or "yaml"
    recording_autosave = os.getenv("RECORDING_AUTOSAVE", "true").lower() == "true"

    generator_config_path = os.getenv("GENERATOR_CONFIG_PATH")
    forwarder_config_path = os.getenv("FORWARDER_CONFIG_PATH")

    allowed_simulator_modes = ["replay", "record", "generate"]
    if simulator_mode not in allowed_simulator_modes:
        logger.error("SIMULATOR_MODE must be one of %s", allowed_simulator_modes)
        exit(1)

    allowed_recording_formats = ["yaml", "json"]
    if recording_format not in allowed_recording_formats:
        logger.error("RECORDING_FORMAT must be one of %s", allowed_recording_formats)
        exit(1)

    return Config(
        simulator_mode=simulator_mode,
        recording_dir=recording_dir,
        recording_format=recording_format,
        recording_autosave=recording_autosave,
        generator_config_path=generator_config_path,
        forwarder_config_path=forwarder_config_path,
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
        logger.info("📼 Recording directory      : %s", config.recording_dir)
        logger.info("📼 Recording format         : %s", config.recording_format)
        logger.info("📼 Recording auto-save      : %s", config.recording_autosave)
        # TODO - handle JSON loading (or update docs!)
        if config.recording_format != "yaml":
            raise ValueError(f"Unsupported recording format: {config.recording_format}")
        persister = YamlRecordingPersister(config.recording_dir)

        forwarder = None
        forwarder_config_path = config.forwarder_config_path or os.path.join(
            module_path, "record_replay/_request_forwarder_config.py"
        )
        if config.simulator_mode == "record":
            logger.info("📼 Forwarder config path: %s", forwarder_config_path)
            forwarder = RequestForwarder(forwarder_config_path)

        record_replay_handler = RecordReplayHandler(
            simulator_mode=config.simulator_mode,
            persister=persister,
            forwarder=forwarder,
            autosave=config.recording_autosave,
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

    openai_deployments = load_openai_deployments()
    logger.info("📝 Using OpenAI deployments: %s", openai_deployments)

    openai_deployment_limits = (
        {name: deployment.tokens_per_minute for name, deployment in openai_deployments.items()}
        if openai_deployments
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
            context = RequestContext(request)

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
