"""
Test the OpenAI generator endpoints
"""

from aoai_simulated_api.app_builder import Config
from openai import AzureOpenAI
import pytest

from .test_uvicorn_server import UvicornTestServer


def _get_generator_config() -> Config:
    return Config(
        simulator_mode="generate",
        recording_autosave=False,
        recording_dir="",
        recording_format="",
        forwarder_config_path="",
        generator_config_path="",
    )


@pytest.mark.asyncio
async def test_openai_generator_completion():
    """
    Ensure we can call the completion endpoint using the generator
    """
    config = _get_generator_config()
    server = UvicornTestServer(config)
    with server.run_in_thread():
        aoai_client = AzureOpenAI(
            api_key="123456789",
            api_version="2023-12-01-preview",
            azure_endpoint="http://localhost:8001",
            max_retries=0,
        )
        prompt = "This is a test prompt"
        response = aoai_client.completions.create(model="deployment1", prompt=prompt, max_tokens=50)

        assert len(response.choices) == 1
        assert len(response.choices[0].text) > 50


@pytest.mark.asyncio
async def test_openai_generator_chat_completion():
    """
    Ensure we can call the chat completion endpoint using the generator
    """
    config = _get_generator_config()
    server = UvicornTestServer(config)
    with server.run_in_thread():
        aoai_client = AzureOpenAI(
            api_key="123456789",
            api_version="2023-12-01-preview",
            azure_endpoint="http://localhost:8001",
            max_retries=0,
        )
        messages = [{"role": "user", "content": "What is the meaning of life?"}]
        response = aoai_client.chat.completions.create(model="deployment1", messages=messages, max_tokens=50)

        assert len(response.choices) == 1
        assert response.choices[0].message.role == "assistant"
        assert len(response.choices[0].message.content) > 20


@pytest.mark.asyncio
async def test_openai_generator_embeddings():
    """
    Ensure we can call the embeddings endpoint using the generator
    """
    config = _get_generator_config()
    server = UvicornTestServer(config)
    with server.run_in_thread():
        aoai_client = AzureOpenAI(
            api_key="123456789",
            api_version="2023-12-01-preview",
            azure_endpoint="http://localhost:8001",
            max_retries=0,
        )
        content = "This is some text to generate embeddings for"
        response = aoai_client.embeddings.create(model="deployment1", input=content)

        assert len(response.data) == 1
        assert response.data[0].object == "embedding"
        assert response.data[0].index == 0
        assert len(response.data[0].embedding) == 1536
