import logging
import os
from locust import HttpUser, task, constant, events
from locust.env import Environment

from common.config import api_key
from common.latency import set_simulator_chat_completions_latency


max_tokens = int(os.getenv("MAX_TOKENS", "100"))
deployment_name = "gpt-35-turbo-100m-token"


@events.init.add_listener
def on_locust_init(environment: Environment, **_):
    """
    Configure test
    """
    logging.info("on_locust_init: %s", environment.host)
    logging.info("Using max_tokens = %d", max_tokens)

    logging.info("Set chat completion latencies to zero")
    set_simulator_chat_completions_latency(environment.host, mean=0, std_dev=0)

    logging.info("on_locust_init - done")


class ChatCompletionsNoLimitUser(HttpUser):
    wait_time = constant(1)  # wait 1 second between requests

    @task
    def hello_world(self):
        url = f"openai/deployments/{deployment_name}/chat/completions?api-version=2023-05-15"
        # Using a large payload to trigger the >1000 tokens per request threshold
        # This is needed to test the rate limiting logic using tokens
        payload = {
            "messages": [
                {"role": "user", "content": "Lorem ipsum dolor sit amet?"},
            ],
            "model": "gpt-35-turbo",
            "max_tokens": max_tokens,
        }
        self.client.post(
            url,
            json=payload,
            headers={"api-key": api_key},
        )