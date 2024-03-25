import asyncio
import logging
import os
import traceback
from typing import Callable
from fastapi import FastAPI, Request, Response
from limits import storage

import constants
from config import load_openai_deployments, load_doc_intelligence_limit, setup_tiktoken_cache
from generator import GeneratorManager
from limiters import create_openai_limiter, create_doc_intelligence_limiter
from pipeline import RequestContext
from record_replay import RecordReplayHandler, YamlRecordingPersister, RequestForwarder

simulator_mode = os.getenv("SIMULATOR_MODE") or "replay"
recording_dir = os.getenv("RECORDING_DIR") or ".recording"
recording_dir = os.path.abspath(recording_dir)
recording_format = os.getenv("RECORDING_FORMAT") or "yaml"
recording_autosave = os.getenv("RECORDING_AUTOSAVE", "true").lower() == "true"
use_tiktoken_cache = os.getenv("USE_TIKTOKEN_CACHE", "false").lower() == "true"

generator_config_path = os.getenv("GENERATOR_CONFIG_PATH") or "generator/default_config.py"
forwarder_config_path = os.getenv("FORWARDER_CONFIG_PATH") or "record_replay/_request_forwarder_config.py"

log_level = os.getenv("LOG_LEVEL") or "INFO"

if use_tiktoken_cache:
    setup_tiktoken_cache()

logger = logging.getLogger(__name__)
logging.basicConfig(level=log_level)

allowed_simulator_modes = ["replay", "record", "generate"]
if simulator_mode not in allowed_simulator_modes:
    logger.error(f"SIMULATOR_MODE must be one of %s", allowed_simulator_modes)
    exit(1)

allowed_recording_formats = ["yaml", "json"]
if recording_format not in allowed_recording_formats:
    logger.error(f"RECORDING_FORMAT must be one of %s", allowed_recording_formats)
    exit(1)

logger.info("🚀 Starting aoai-simulated-api in %s mode", simulator_mode)

app = FastAPI()

if simulator_mode == "generate":
    logger.info(f"📝 Generator config path: %s", generator_config_path)
    generator_manager = GeneratorManager(generator_config_path=generator_config_path)
else:
    logger.info(f"📼 Recording directory: %s", recording_dir)
    logger.info(f"📼 Recording format   : %s", recording_format)
    logger.info(f"📼 Recording auto-save: %s", recording_autosave)
    # TODO - handle JSON loading (or update docs!)
    if recording_format != "yaml":
        raise Exception(f"Unsupported recording format: {recording_format}")
    persister = YamlRecordingPersister(recording_dir)

    forwarder = None
    if simulator_mode == "record":
        forwarder = RequestForwarder(forwarder_config_path)

    record_replay_handler = RecordReplayHandler(
        simulator_mode=simulator_mode, persister=persister, forwarder=forwarder, autosave=recording_autosave
    )


@app.get("/")
async def root():
    return {"message": "👋 aoai-simulated-api is running"}


@app.post("/++/save-recordings")
def save_recordings():
    if simulator_mode == "record":
        logger.info("📼 Saving recordings...")
        record_replay_handler.save_recordings()
        logger.info("📼 Recordings saved")
        return Response(content="📼 Recordings saved", status_code=200)
    else:
        logger.warn("⚠️ Not saving recordings as not in record mode")
        return Response(content="⚠️ Not saving recordings as not in record mode", status_code=400)


memory_storage = storage.MemoryStorage()

doc_intelligence_rps = load_doc_intelligence_limit()
logger.info(f"📝 Using Doc Intelligence RPS: %s", doc_intelligence_rps)

openai_deployments = load_openai_deployments()
logger.info(f"📝 Using OpenAI deployments: %s", openai_deployments)


openai_deployment_limits = (
    {name: deployment.tokens_per_minute for name, deployment in openai_deployments.items()}
    if openai_deployments
    else {}
)
# Dictionary of limiters keyed by name
# Each limiter is a function that takes a response and returns a boolean indicating whether the request should be allowed
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

        if simulator_mode == "generate":
            response = await generator_manager.generate(context)

        if simulator_mode in ["record", "replay"]:
            response = await record_replay_handler.handle_request(context)

        if not response:
            raise Exception("response not set")

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
        # TODO - move these header values to RequestContext to share (then they don't need removing here!)
        for key, _ in request.headers.items():
            if key.startswith(constants.SIMULATOR_HEADER_PREFIX):
                del response.headers[key]

        return response
    except Exception as e:
        logger.error(f"Error: %s\n%s", e, traceback.format_exc())
        return Response(status_code=500)
