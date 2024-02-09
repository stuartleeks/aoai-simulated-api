import os
from fastapi import FastAPI, Request, Response

from vcr_handler import VcrHandler
from generator_manager import GeneratorManager


api_key = os.getenv("AZURE_OPENAI_KEY")
api_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")

simulator_mode = os.getenv("SIMULATOR_MODE") or "replay"
recording_dir = os.getenv("RECORDING_DIR") or ".recording"
recording_dir = os.path.abspath(recording_dir)
recording_format = os.getenv("RECORDING_FORMAT") or "yaml"

generator_config_path = os.getenv("GENERATOR_CONFIG_PATH") or "generator_config.py"

if api_key is None:
    print("AZURE_OPENAI_KEY is not set", flush=True)
    exit(1)

if api_endpoint is None:
    print("AZURE_OPENAI_ENDPOINT is not set", flush=True)
    exit(1)

allowed_simulator_modes = ["replay", "record", "generate"]
if simulator_mode not in allowed_simulator_modes:
    print(f"SIMULATOR_MODE must be one of {allowed_simulator_modes}", flush=True)
    exit(1)

allowed_recording_formats = ["yaml", "json"]
if recording_format not in allowed_recording_formats:
    print(f"RECORDING_FORMAT must be one of {allowed_recording_formats}", flush=True)
    exit(1)

print(f"🚀 Starting aoai-simulated-api in {simulator_mode} mode", flush=True)
print(f"📼 Recording directory: {recording_dir}", flush=True)
print(f"📼 Recording format: {recording_format}", flush=True)
print(f"🔑 API endpoint: {api_endpoint}", flush=True)
masked_api_key = api_key[:4] + "..." + api_key[-4:]
print(f"🔑 API key: {masked_api_key}", flush=True)
print(f"🔌 Generator config path: {generator_config_path}", flush=True)


app = FastAPI()

if simulator_mode == "generate":
    generator_manager = GeneratorManager(generator_config_path=generator_config_path)
else:
    vcr_handler = VcrHandler(
        api_endpoint=api_endpoint,
        api_key=api_key,
        simulator_mode=simulator_mode,
        recording_dir=recording_dir,
        recording_format=recording_format,
    )


@app.get("/")
async def root():
    return {"message": "👋 aoai-simulated-api is running"}


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def catchall(request: Request):
    print("⚠️ handling route: " + request.url.path, flush=True)

    try:
        if simulator_mode == "generate":
            return await generator_manager.generate(request)

        if simulator_mode in ["record", "replay"]:
            return await vcr_handler.handle_request_with_vcr(request)
    except Exception as e:
        print(f"Error: {e}", flush=True)
        return Response(status_code=500)
