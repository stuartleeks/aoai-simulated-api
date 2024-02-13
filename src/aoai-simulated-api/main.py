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


allowed_simulator_modes = ["replay", "record", "generate"]
if simulator_mode not in allowed_simulator_modes:
    print(f"SIMULATOR_MODE must be one of {allowed_simulator_modes}", flush=True)
    exit(1)

allowed_recording_formats = ["yaml", "json"]
if recording_format not in allowed_recording_formats:
    print(f"RECORDING_FORMAT must be one of {allowed_recording_formats}", flush=True)
    exit(1)

print(f"🚀 Starting aoai-simulated-api in {simulator_mode} mode", flush=True)

app = FastAPI()

if simulator_mode == "generate":
    print(f"🔌 Generator config path: {generator_config_path}", flush=True)
    generator_manager = GeneratorManager(generator_config_path=generator_config_path)
else:
    print(f"📼 Recording directory: {recording_dir}", flush=True)
    print(f"📼 Recording format   : {recording_format}", flush=True)
    print(f"📼 Recording auto-save: {recording_autosave}", flush=True)
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
        print("📼 Saving recordings...", flush=True)
        record_replay_handler.save_recordings()
        print("📼 Recordings saved", flush=True)
        return Response(content="📼 Recordings saved", status_code=200)
    else:
        print("⚠️ Not saving recordings as not in record mode", flush=True)
        return Response(content="⚠️ Not saving recordings as not in record mode", status_code=400)


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def catchall(request: Request):
    print("⚡ handling route: " + request.url.path, flush=True)

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
        print(f"Error: {e}\n{traceback.format_exc()}", flush=True)
        return Response(status_code=500)
