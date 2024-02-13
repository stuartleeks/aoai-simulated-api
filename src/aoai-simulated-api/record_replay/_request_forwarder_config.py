import os
from typing import Callable
import fastapi
import requests

# This file contains a default implementation of the get_forwarders function
# for handling forwarded requests
# You can configure your own forwarders by creating a forwarder_config.py file and setting the
# FORWWARDER_CONFIG_PATH environment variable to the path of the file when running the API
# See src/example_forwarder_config/forwarder_config.py for an example of how to define your own forwarders

aoai_api_key: str | None = None
aoai_api_endpoint: str | None = None
aoai_initialized: bool = False


def initialize_azure_openai():
    global aoai_api_key, aoai_api_endpoint, aoai_initialized
    aoai_api_key = os.getenv("AZURE_OPENAI_KEY")
    aoai_api_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")

    aoai_initialized = True

    if aoai_api_key and aoai_api_endpoint:
        print(f"🚀 Initialized Azure OpenAI forwarder with the following settings:", flush=True)
        print(f"🔑 API endpoint: {aoai_api_endpoint}", flush=True)
        masked_api_key = aoai_api_key[:4] + "..." + aoai_api_key[-4:]
        print(f"🔑 API key: {masked_api_key}", flush=True)

    else:
        print(
            f"Got a request that looked like an openai request, but missing some or all of the required environment variables for forwarding: AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY",
            flush=True,
        )


aoai_response_headers_to_remove = [
    # Strip out header values we aren't interested in - this also helps to reduce the recording file size
    "apim-request-id",
    "azureml-model-session",
    "x-accel-buffering",
    "x-content-type-options",
    "x-ms-client-request-id",
    "x-ms-region",
    "x-request-id",
    "Cache-Control",
    "Content-Length",
    "Date",
    "Strict-Transport-Security",
    "access-control-allow-origin",
    # "x-ratelimit-remaining-requests",
    # "x-ratelimit-remaining-tokens",
]


async def forward_to_azure_openai(request: fastapi.Request) -> fastapi.Response | requests.Response | dict | None:
    if not request.url.path.startswith("/openai/"):
        # assume not an OpenAI request
        return None

    if not aoai_initialized:
        # Only initialize once, and only if we need to
        initialize_azure_openai()

    if aoai_api_key is None or aoai_api_endpoint is None:
        return None

    url = aoai_api_endpoint
    if url.endswith("/"):
        url = url[:-1]
    url += request.url.path + "?" + request.url.query

    # Copy most headers, but override auth
    fwd_headers = {
        k: v for k, v in request.headers.items() if k.lower() not in ["content-length", "host", "authorization"]
    }
    fwd_headers["api-key"] = aoai_api_key

    body = await request.body()

    response = requests.request(
        request.method,
        url,
        headers=fwd_headers,
        data=body,
    )

    for header in aoai_response_headers_to_remove:
        if response.headers.get(header):
            del response.headers[header]

    return response


def get_forwarders() -> list[Callable[[fastapi.Request], fastapi.Response | requests.Response | None]]:
    # Return a list of functions to call when recording and no matching saved request is found
    # If the function returns a Response object (from FastAPI or requests package), it will be used as the response for the request
    # If the function returns a dict then it should have a "response" property with the response and a "persist" property that is True/False to indicate whether to persist the response
    # If the function returns None, the next function in the list will be called
    return [
        forward_to_azure_openai,
    ]
