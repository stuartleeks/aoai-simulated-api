import json
import os
from typing import Callable
import fastapi
from fastapi.datastructures import URL
import requests

# This file is an example of how you can define your request forwarders
# Forwarders can be sync or async methods

doc_intelligence_api_key: str | None = None
doc_intelligence_api_endpoint: str | None = None
doc_intelligence_initialized: bool = False


def initialize_document_intelligence():
    global doc_intelligence_api_key, doc_intelligence_api_endpoint, doc_intelligence_initialized
    doc_intelligence_api_key = os.getenv("AZURE_FORM_RECOGNIZER_KEY")
    doc_intelligence_api_endpoint = os.getenv("AZURE_FORM_RECOGNIZER_ENDPOINT")

    doc_intelligence_initialized = True

    if doc_intelligence_api_key and doc_intelligence_api_endpoint:
        print(f"🚀 Initialized Azure Document Intelligence forwarder with the following settings:", flush=True)
        print(f"🔑 API endpoint: {doc_intelligence_api_endpoint}", flush=True)
        masked_api_key = doc_intelligence_api_key[:4] + "..." + doc_intelligence_api_key[-4:]
        print(f"🔑 API key: {masked_api_key}", flush=True)

    else:
        print(
            f"Got a request that looked like a Document Intelligence request, but missing some or all of the required environment variables for forwarding: AZURE_FORM_RECOGNIZER_ENDPOINT, AZURE_FORM_RECOGNIZER_KEY",
            flush=True,
        )


doc_intelligence_response_headers_to_remove = [
    # Strip out header values we aren't interested in - this also helps to reduce the recording file size
    "apim-request-id",
    "x-content-type-options",
    "x-ms-region",
    "x-envoy-upstream-service-time" "Content-Length",
    "Date",
    "Strict-Transport-Security",
]


async def forward_to_azure_document_intelligence(
    request: fastapi.Request,
) -> fastapi.Response | requests.Response | dict | None:
    if not request.url.path.startswith("/formrecognizer/"):
        # assume not an Doc Intelligence request
        return None

    print("Forwarding Document Intelligence request:" + request.url.path)

    if not doc_intelligence_initialized:
        # Only initialize once, and only if we need to
        initialize_document_intelligence()

    if doc_intelligence_api_key is None or doc_intelligence_api_endpoint is None:
        return None

    persist = True

    url = doc_intelligence_api_endpoint
    if url.endswith("/"):
        url = url[:-1]
    url += request.url.path + "?" + request.url.query

    # Copy most headers, but override auth
    fwd_headers = {
        k: v for k, v in request.headers.items() if k.lower() not in ["content-length", "host", "authorization"]
    }
    fwd_headers["api-key"] = doc_intelligence_api_key

    body = await request.body()

    response = requests.request(
        request.method,
        url,
        headers=fwd_headers,
        data=body,
    )

    for header in doc_intelligence_response_headers_to_remove:
        if response.headers.get(header):
            del response.headers[header]

    if "analyzeResults" in request.url.path:
        if response.status_code == 200:
            # only persist the response if it contains the result
            result = json.loads(response.text)
            persist = result.get("status") != "running"
    else:
        # Set header to indicate which limiter to use
        # Only set on analyze request, not on querying results
        response.headers["X-Simulator-Limiter"] = "docintelligence"

    if "operation-location" in response.headers:
        operation_location = URL(response.headers["operation-location"])
        new_operation_location = "http://localhost:8000" + operation_location.path + "?" + operation_location.query
        response.headers["operation-location"] = new_operation_location

    return {"response": response, "persist": persist}


def get_forwarders() -> list[Callable[[fastapi.Request], fastapi.Response | requests.Response | dict | None]]:
    # Return a list of functions to call when recording and no matching saved request is found
    # If the function returns a Response object (from FastAPI or requests package), it will be used as the response for the request
    # If the function returns a dict then it should have a "response" property with the response and a "persist" property that is True/False to indicate whether to persist the response
    # If the function returns None, the next function in the list will be called
    return [
        forward_to_azure_document_intelligence,
    ]
