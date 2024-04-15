"""
Test the OpenAI generator endpoints
"""

import shutil
import tempfile
from aoai_simulated_api.models import Config, RecordingConfig
from openai import AzureOpenAI
import pytest
from pytest_httpserver import HTTPServer

from .test_uvicorn_server import UvicornTestServer

from aoai_simulated_api.record_replay import get_default_forwarders


class TempDirectory:
    _temp_dir: str | None = None
    _prefix: str

    def __init__(self, prefix: str = "aoai-simulated-api-test-"):
        self._prefix = prefix

    def __enter__(self):
        self._temp_dir = tempfile.mkdtemp(prefix=self._prefix)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):

        shutil.rmtree(self._temp_dir)

    @property
    def path(self):
        return self._temp_dir


API_KEY = "123456879"


def _get_record_config(httpserver: HTTPServer, recording_path: str) -> Config:
    forwarding_server_url = httpserver.url_for("/").removesuffix("/")
    return Config(
        simulator_mode="record",
        simulator_api_key=API_KEY,
        recording=RecordingConfig(
            autosave=True,
            dir=recording_path,
            aoai_api_endpoint=forwarding_server_url,
            aoai_api_key="123456789",
            forwarders=get_default_forwarders(),
        ),
        generators=[],
        openai_deployments=None,
        doc_intelligence_rps=123,
    )


def _get_replay_config(recording_path: str) -> Config:
    return Config(
        simulator_mode="replay",
        simulator_api_key=API_KEY,
        recording=RecordingConfig(
            autosave=True,
            dir=recording_path,
            forwarders=get_default_forwarders(),
        ),
        openai_deployments=None,
        generators=[],
        doc_intelligence_rps=123,
    )


@pytest.mark.asyncio
async def test_openai_record_replay_completion(httpserver: HTTPServer):
    """
    Ensure we can call the completion endpoint using the record mode
    """

    # Set up pytest-httpserver to provide an endpoint for the simulator
    # to call in record mode
    httpserver.expect_request(
        uri="/openai/deployments/deployment1/completions",
        query_string="api-version=2023-12-01-preview",
        method="POST",
    ).respond_with_data(
        '{"id":"cmpl-95FbXadIqJEMZZ1Rl0chTcKRxk2ez","object":"text_completion","created":1711038651,"model":"gpt-35-turbo","prompt_filter_results":[{"prompt_index":0,"content_filter_results":{"hate":{"filtered":false,"severity":"safe"},"self_harm":{"filtered":false,"severity":"safe"},"sexual":{"filtered":false,"severity":"safe"},"violence":{"filtered":false,"severity":"safe"}}}],"choices":[{"text":"This is a test","index":0,"finish_reason":"length","logprobs":null,"content_filter_results":{"hate":{"filtered":false,"severity":"safe"},"self_harm":{"filtered":false,"severity":"safe"},"sexual":{"filtered":false,"severity":"safe"},"violence":{"filtered":false,"severity":"safe"}}}],"usage":{"prompt_tokens":7,"completion_tokens":50,"total_tokens":57}}\n'
    )
    httpserver.expect_request("/hello").respond_with_data("Hello, world!")

    def test_completion_call(config):
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
            assert response.choices[0].text == "This is a test"

    with TempDirectory() as temp_dir:
        # set up simulated API in record mode
        config = _get_record_config(httpserver, temp_dir.path)
        test_completion_call(config)

        # Undo httpserver config to ensure there isn't an endpoint to forward to
        # when testing in replay mode
        httpserver.clear_all_handlers()

        # set up simulated API in replay mode (using the recording from above)
        config = _get_replay_config(temp_dir.path)
        test_completion_call(config)
