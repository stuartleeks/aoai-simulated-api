"""
Test the OpenAI generator endpoints
"""

import os
from aoai_simulated_api.config_loader import load_extension
from aoai_simulated_api.models import (
    Config,
    LatencyConfig,
    ChatCompletionLatency,
    CompletionLatency,
    EmbeddingLatency,
)
from aoai_simulated_api.generator.manager import get_default_generators
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import ClientAuthenticationError
from azure.ai.formrecognizer import DocumentAnalysisClient
import pytest

from .test_uvicorn_server import UvicornTestServer

API_KEY = "123456789"


def _get_generator_config() -> Config:
    config = Config(generators=get_default_generators())
    config.simulator_api_key = API_KEY
    config.simulator_mode = "generate"
    config.latency = LatencyConfig(
        open_ai_completions=CompletionLatency(
            LATENCY_OPENAI_COMPLETIONS_MEAN=0,
            LATENCY_OPENAI_COMPLETIONS_STD_DEV=0.1,
        ),
        open_ai_chat_completions=ChatCompletionLatency(
            LATENCY_OPENAI_CHAT_COMPLETIONS_MEAN=0,
            LATENCY_OPENAI_CHAT_COMPLETIONS_STD_DEV=0.1,
        ),
        open_ai_embeddings=EmbeddingLatency(
            LATENCY_OPENAI_EMBEDDINGS_MEAN=0,
            LATENCY_OPENAI_EMBEDDINGS_STD_DEV=0.1,
        ),
    )
    load_extension(config=config, extension_path="src/examples/generator_doc_intelligence")

    return config


@pytest.mark.asyncio
async def test_requires_auth():
    """
    Ensure we need the right API key to call the completion endpoint
    """
    config = _get_generator_config()
    server = UvicornTestServer(config)
    with server.run_in_thread():
        credential = AzureKeyCredential("wrong_key")
        document_analysis_client = DocumentAnalysisClient("http://localhost:8001", credential)

        base_path = os.path.dirname(os.path.realpath(__file__))
        pdf_path = os.path.join(base_path, "../test-client/receipt.png")

        try:
            print("Making request...")
            with open(pdf_path, "rb") as f:
                document_analysis_client.begin_analyze_document("prebuilt-receipt", f)

            assert False, "Should get exception"
        except ClientAuthenticationError as e:
            assert e.status_code == 401
            assert e.message == "Operation returned an invalid status 'Unauthorized'"


@pytest.mark.asyncio
async def test_gets_result():
    """
    Ensure we need the right API key to call the completion endpoint
    """
    config = _get_generator_config()
    server = UvicornTestServer(config)
    with server.run_in_thread():
        credential = AzureKeyCredential(API_KEY)
        document_analysis_client = DocumentAnalysisClient("http://localhost:8001", credential)

        base_path = os.path.dirname(os.path.realpath(__file__))
        pdf_path = os.path.join(base_path, "../test-client/receipt.png")

        print("Making request...")
        with open(pdf_path, "rb") as f:
            poller = document_analysis_client.begin_analyze_document("prebuilt-receipt", f)

        print("Polling for result...")
        result = poller.result()
        print("Poller result: ", result)
