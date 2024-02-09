import os
from fastapi import FastAPI, Request, Response

from vcr_handler import VcrHandler
from generator_manager import GeneratorManager


api_key = os.getenv("AZURE_OPENAI_KEY")
api_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")

simulator_mode = os.getenv("SIMULATOR_MODE") or "replay"
cassette_dir = os.getenv("CASSETTE_DIR") or ".cassettes"
cassette_dir = os.path.abspath(cassette_dir)
cassette_format = os.getenv("CASSETTE_FORMAT") or "yaml"

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

allowed_cassette_formats = ["yaml", "json"]
if cassette_format not in allowed_cassette_formats:
    print(f"CASSETTE_FORMAT must be one of {allowed_cassette_formats}", flush=True)
    exit(1)

print(f"🚀 Starting aoai-simulated-api in {simulator_mode} mode", flush=True)
print(f"📼 Cassette directory: {cassette_dir}", flush=True)
print(f"📼 Cassette format: {cassette_format}", flush=True)
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
        cassette_dir=cassette_dir,
        cassette_format=cassette_format,
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
