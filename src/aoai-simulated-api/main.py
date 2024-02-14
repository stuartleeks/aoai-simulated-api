import logging
import os
import traceback
from fastapi import FastAPI, Request, Response

from generator import GeneratorManager
from record_replay import RecordReplayHandler, YamlRecordingPersister, RequestForwarder

simulator_mode = os.getenv("SIMULATOR_MODE") or "replay"
recording_dir = os.getenv("RECORDING_DIR") or ".recording"
recording_dir = os.path.abspath(recording_dir)
recording_format = os.getenv("RECORDING_FORMAT") or "yaml"
recording_autosave = os.getenv("RECORDING_AUTOSAVE", "true").lower() == "true"

generator_config_path = os.getenv("GENERATOR_CONFIG_PATH") or "generator/config.py"
forwarder_config_path = os.getenv("FORWARDER_CONFIG_PATH") or "record_replay/_request_forwarder_config.py"

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)  # TODO - make this configurable

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
    logger.info(f"🔌 Generator config path: %s", generator_config_path)
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


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def catchall(request: Request):
    logger.debug("⚡ handling route: %s", request.url.path)

    try:
        response = None

        if simulator_mode == "generate":
            response = await generator_manager.generate(request)

        if simulator_mode in ["record", "replay"]:
            response = await record_replay_handler.handle_request(request)

        if not response:
            raise Exception("response not set")

        return response
    except Exception as e:
        logger.error(f"Error: %s\n%s", e, traceback.format_exc())
        return Response(status_code=500)
