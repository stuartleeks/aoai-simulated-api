"""
Test the OpenAI generator endpoints
"""

from aoai_simulated_api.models import (
    Config,
    LatencyConfig,
    ChatCompletionLatency,
    CompletionLatency,
    EmbeddingLatency,
    OpenAIDeployment,
)
from aoai_simulated_api.generator.manager import get_default_generators
from openai import AzureOpenAI, AuthenticationError, RateLimitError
import pytest

from .test_uvicorn_server import UvicornTestServer

API_KEY = "123456789"


def _get_generator_config(extension_path: str | None = None) -> Config:
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
    config.openai_deployments = {
        "low_limit": OpenAIDeployment(name="low_limit", model="gpt-3.5-turbo", tokens_per_minute=64 * 6)
    }
    config.extension_path = extension_path
    return config


@pytest.mark.asyncio
async def test_openai_generator_completion_requires_auth():
    """
    Ensure we need the right API key to call the completion endpoint
    """
    config = _get_generator_config()
    server = UvicornTestServer(config)
    with server.run_in_thread():
        aoai_client = AzureOpenAI(
            api_key="wrong_key",
            api_version="2023-12-01-preview",
            azure_endpoint="http://localhost:8001",
            max_retries=0,
        )
        prompt = "This is a test prompt"

        try:
            aoai_client.completions.create(model="deployment1", prompt=prompt, max_tokens=50)
            assert False, "Expected an exception"
        except AuthenticationError as e:
            assert e.status_code == 401
            assert e.message == "Error code: 401 - {'detail': 'Missing or incorrect API Key'}"


@pytest.mark.asyncio
async def test_openai_generator_completion_success():
    """
    Ensure we can call the completion endpoint using the generator
    """
    config = _get_generator_config()
    server = UvicornTestServer(config)
    with server.run_in_thread():
        aoai_client = AzureOpenAI(
            api_key=API_KEY,
            api_version="2023-12-01-preview",
            azure_endpoint="http://localhost:8001",
            max_retries=0,
        )
        prompt = "This is a test prompt"
        response = aoai_client.completions.create(model="deployment1", prompt=prompt, max_tokens=50)

        assert len(response.choices) == 1
        assert len(response.choices[0].text) > 50


@pytest.mark.asyncio
async def test_openai_generator_chat_completion_requires_auth():
    """
    Ensure we need the right API key to call the chat completion endpoint
    """
    config = _get_generator_config()
    server = UvicornTestServer(config)
    with server.run_in_thread():
        aoai_client = AzureOpenAI(
            api_key="wrong_key",
            api_version="2023-12-01-preview",
            azure_endpoint="http://localhost:8001",
            max_retries=0,
        )
        messages = [{"role": "user", "content": "What is the meaning of life?"}]

        try:
            aoai_client.chat.completions.create(model="deployment1", messages=messages, max_tokens=50)
            assert False, "Expected an exception"
        except AuthenticationError as e:
            assert e.status_code == 401
            assert e.message == "Error code: 401 - {'detail': 'Missing or incorrect API Key'}"


@pytest.mark.asyncio
async def test_openai_generator_chat_completion_success():
    """
    Ensure we can call the chat completion endpoint using the generator
    """
    config = _get_generator_config()
    server = UvicornTestServer(config)
    with server.run_in_thread():
        aoai_client = AzureOpenAI(
            api_key=API_KEY,
            api_version="2023-12-01-preview",
            azure_endpoint="http://localhost:8001",
            max_retries=0,
        )
        messages = [{"role": "user", "content": "What is the meaning of life?"}]
        response = aoai_client.chat.completions.create(model="deployment1", messages=messages, max_tokens=50)

        assert len(response.choices) == 1
        assert response.choices[0].message.role == "assistant"
        assert len(response.choices[0].message.content) > 20
        assert response.choices[0].finish_reason == "length"


@pytest.mark.asyncio
async def test_openai_generator_embeddings_requires_auth():
    """
    Ensure we need the right API key to call the embeddings endpoint
    """
    config = _get_generator_config()
    server = UvicornTestServer(config)
    with server.run_in_thread():
        aoai_client = AzureOpenAI(
            api_key="wrong_key",
            api_version="2023-12-01-preview",
            azure_endpoint="http://localhost:8001",
            max_retries=0,
        )
        content = "This is some text to generate embeddings for"

        try:
            aoai_client.embeddings.create(model="deployment1", input=content)
            assert False, "Expected an exception"
        except AuthenticationError as e:
            assert e.status_code == 401
            assert e.message == "Error code: 401 - {'detail': 'Missing or incorrect API Key'}"


@pytest.mark.asyncio
async def test_openai_generator_embeddings_success():
    """
    Ensure we can call the embeddings endpoint using the generator
    """
    config = _get_generator_config()
    server = UvicornTestServer(config)
    with server.run_in_thread():
        aoai_client = AzureOpenAI(
            api_key=API_KEY,
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


@pytest.mark.asyncio
async def test_openai_generator_chat_completion_with_custom_generator():
    """
    Ensure we can call the chat completion endpoint using a generator from an extension
    """
    config = _get_generator_config(extension_path="src/examples/generator_replace_chat_completion/generator_config.py")

    server = UvicornTestServer(config)
    with server.run_in_thread():
        aoai_client = AzureOpenAI(
            api_key=API_KEY,
            api_version="2023-12-01-preview",
            azure_endpoint="http://localhost:8001",
            max_retries=0,
        )
        messages = [{"role": "user", "content": "What is the meaning of life?"}]
        response = aoai_client.chat.completions.create(model="deployment1", messages=messages, max_tokens=50)

        assert len(response.choices) == 1
        assert response.choices[0].message.role == "assistant"
        assert len(response.choices[0].message.content.split(" ")) == 1
        assert response.choices[0].finish_reason == "stop"


@pytest.mark.asyncio
async def test_openai_generator_embeddings_limit_reached():
    """
    Ensure we can call the chat completions endpoint multiple times using the generator to trigger rate-limiting
    """
    config = _get_generator_config()
    server = UvicornTestServer(config)
    with server.run_in_thread():
        aoai_client = AzureOpenAI(
            api_key=API_KEY,
            api_version="2023-12-01-preview",
            azure_endpoint="http://localhost:8001",
            max_retries=0,
        )
        messages = [{"role": "user", "content": "What is the meaning of life?"}]
        response = aoai_client.chat.completions.create(model="low_limit", messages=messages, max_tokens=50)

        assert len(response.choices) == 1
        assert response.choices[0].message.role == "assistant"
        assert len(response.choices[0].message.content) > 20
        assert response.choices[0].finish_reason == "length"

        # The total token count for the request is roughly 60 tokens
        # "low_limit" deployment has a rate limit of 600 tokens per minute
        # Which is 100 every 10s, so our second request should trigger the rate-limiting
        try:
            aoai_client.chat.completions.create(model="low_limit", messages=messages, max_tokens=50)
            assert False, "Expect to be rate-limited"
        except RateLimitError as e:
            assert e.status_code == 429
            assert (
                e.message
                == "Error code: 429 - {'error': {'code': '429', 'message': 'Requests to the OpenAI API Simulator have exceeded call rate limit. Please retry after 10 seconds.'}}"
            )
