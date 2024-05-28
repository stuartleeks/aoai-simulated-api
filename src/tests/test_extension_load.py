"""
Test extension loading
"""

from aoai_simulated_api.config_loader import load_extension
from aoai_simulated_api.generator.manager import get_default_generators
from aoai_simulated_api.models import (
    Config,
    LatencyConfig,
    ChatCompletionLatency,
    CompletionLatency,
    EmbeddingLatency,
)
import pytest
import requests

from .test_uvicorn_server import UvicornTestServer

from aoai_simulated_api.record_replay.handler import get_default_forwarders

API_KEY = "123456789"


def _get_config() -> Config:
    config = Config(generators=get_default_generators())
    config.simulator_api_key = API_KEY
    config.simulator_mode = "generate"
    config.recording.forwarders = get_default_forwarders()
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
    return config


@pytest.mark.asyncio
async def test_load_extension_from_single_file():
    """
    Ensure we can load a single file extension
    """

    config = _get_config()

    initial_generator_count = len(config.generators)
    load_extension(config=config, extension_path="src/examples/generator_echo/generator_config.py")

    # check that we have an additional generator
    assert len(config.generators) == initial_generator_count + 1
    assert config.generators[-1].__name__ == "generate_echo_response"

    # Check that the generator is called
    server = UvicornTestServer(config)
    with server.run_in_thread():
        response = requests.post(
            "http://localhost:8001/echo",
            timeout=10,
            data="hello",
            headers={"api-key": API_KEY},
        )
        assert response.status_code == 200
        assert response.text == "Echo: hello"


@pytest.mark.asyncio
async def test_load_extension_from_directory():
    """
    Ensure we can load a single file extension
    """

    config = _get_config()

    initial_forwarder_count = len(config.recording.forwarders)
    load_extension(config=config, extension_path="src/examples/forwarder_doc_intelligence")

    # check that we have an additional generator
    assert len(config.recording.forwarders) == initial_forwarder_count + 1
    assert config.recording.forwarders[-1].__name__ == "forward_to_azure_document_intelligence"


@pytest.mark.asyncio
async def test_load_extension_from_directory_init_py():
    """
    Ensure we can load a single file extension
    """

    config = _get_config()

    initial_forwarder_count = len(config.recording.forwarders)
    load_extension(config=config, extension_path="src/examples/forwarder_doc_intelligence/__init__.py")

    # check that we have an additional generator
    assert len(config.recording.forwarders) == initial_forwarder_count + 1
    assert config.recording.forwarders[-1].__name__ == "forward_to_azure_document_intelligence"
