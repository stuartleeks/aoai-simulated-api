"""
Provides the UvicornTestServer class for in-proc testing of the simulator API
"""

import contextlib
import logging
import threading
import time
import pytest
import requests
import uvicorn

from aoai_simulated_api.app_builder import Config, get_simulator

logger = logging.getLogger("tests")


class UvicornTestServer(uvicorn.Server):
    """
    A subclass of Uvicorn's Server class that allows running the server in a separate thread
    to enable running the server in-process during tests
    """

    def __init__(self, config: Config):
        app = get_simulator(logger=logger, config=config)
        uvconfig = uvicorn.Config(app, host="127.0.0.1", port=8001, loop="asyncio")

        super().__init__(uvconfig)
        self.started = False
        self.should_exit = False

    @contextlib.contextmanager
    def run_in_thread(self):
        """
        Run the server in a separate thread
        (based on https://github.com/encode/uvicorn/discussions/1103#discussioncomment-941726)
        """
        thread = threading.Thread(target=self.run)
        thread.start()
        try:
            while not self.started:
                time.sleep(1e-3)
            yield
        finally:
            self.should_exit = True
            thread.join()


@pytest.mark.asyncio
async def test_root_message():
    # This mostly validates that the UvicornTestServer starts up the simulator :-)

    config = Config(
        simulator_mode="generate",
        recording_autosave=False,
        recording_dir="",
        recording_format="",
        forwarder_config_path="",
        generator_config_path="",
    )
    server = UvicornTestServer(config)
    with server.run_in_thread():
        response = requests.get("http://localhost:8001/", timeout=10)
        assert response.status_code == 200
        assert b"aoai-simulated-api is running" in response.content
