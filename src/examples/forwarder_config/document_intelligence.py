import json
import logging
import os
from aoai_simulated_api import constants
from aoai_simulated_api.pipeline import RequestContext
import fastapi
from fastapi.datastructures import URL
import requests

# This file is an example of how you can define your request forwarders
# Forwarders can be sync or async methods

doc_intelligence_api_key: str | None = None
doc_intelligence_api_endpoint: str | None = None
doc_intelligence_initialized: bool = False

logger = logging.getLogger(__name__)


def initialize_document_intelligence():
    global doc_intelligence_api_key, doc_intelligence_api_endpoint, doc_intelligence_initialized
    doc_intelligence_api_key = os.getenv("AZURE_FORM_RECOGNIZER_KEY")
    doc_intelligence_api_endpoint = os.getenv("AZURE_FORM_RECOGNIZER_ENDPOINT")

    doc_intelligence_initialized = True

    if doc_intelligence_api_key and doc_intelligence_api_endpoint:
        logger.info("🚀 Initialized Azure Document Intelligence forwarder with the following settings:")
        logger.info("🔑 API endpoint: %s", doc_intelligence_api_endpoint)
        masked_api_key = doc_intelligence_api_key[:4] + "..." + doc_intelligence_api_key[-4:]
        logger.info("🔑 API key: %s", masked_api_key)

    else:
        logger.warning(
            "Got a request that looked like a Document Intelligence request, "
            + "but missing some or all of the required environment variables for forwarding: "
            + "AZURE_FORM_RECOGNIZER_ENDPOINT, AZURE_FORM_RECOGNIZER_KEY",
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
    context: RequestContext,
) -> fastapi.Response | requests.Response | dict | None:
    request = context.request
    if not request.url.path.startswith("/formrecognizer/"):
        # assume not an Doc Intelligence request
        return None

    logger.debug("Forwarding Document Intelligence request: %s", request.url.path)

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
        context.values[constants.SIMULATOR_KEY_LIMITER] = "docintelligence"

    if "operation-location" in response.headers:
        operation_location = URL(response.headers["operation-location"])
        new_operation_location = "http://localhost:8000" + operation_location.path + "?" + operation_location.query
        response.headers["operation-location"] = new_operation_location

    return {"response": response, "persist": persist}
