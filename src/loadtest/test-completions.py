import os
import time
from locust import User, HttpUser, task, constant
from openai import AzureOpenAI


# aoai_client = AzureOpenAI(
#     api_key="1234567890", api_version="2023-12-01-preview", azure_endpoint="http://localhost:8000", max_retries=0
# )

api_key = os.getenv("SIMULATOR_API_KEY")


class QuickstartUser(HttpUser):
    wait_time = constant(1)

    @task
    def hello_world(self):
        # response = aoai_client.completions.create(model="gpt-35-turbo", prompt="A good DAD joke is ....", max_tokens=50)
        payload = '{"model": "gpt-5-turbo-1","prompt": "Once upon a time","max_tokens": 10}'
        response = self.client.post(
            "openai/deployments/gpt-35-turbo/completions?api-version=2023-05-15",
            data=payload,
            headers={"api-key": api_key},
        )
        response.raise_for_status()
