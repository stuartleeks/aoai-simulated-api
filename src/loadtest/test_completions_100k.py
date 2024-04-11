import os
from locust import HttpUser, task, constant


api_key = os.getenv("SIMULATOR_API_KEY")


class Completions100kUser(HttpUser):
    wait_time = constant(1)  # wait 1 second between requests

    @task
    def hello_world(self):
        deployment_name = "gpt-35-turbo-100k-token"
        url = f"openai/deployments/{deployment_name}/completions?api-version=2023-05-15"
        payload = {"model": "gpt-5-turbo-1", "prompt": "Once upon a time", "max_tokens": 10}
        self.client.post(
            url,
            json=payload,
            headers={"api-key": api_key},
        )
