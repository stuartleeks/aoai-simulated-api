import os
from openai import AzureOpenAI


api_key = os.getenv("AZURE_OPENAI_KEY")
api_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")

print("Connecting to: " + api_endpoint)
client = AzureOpenAI(
    api_key=api_key, api_version="2023-12-01-preview", azure_endpoint=api_endpoint
)

# This will correspond to the custom name you chose for your deployment when you deployed a model. Use a gpt-35-turbo-instruct deployment.
deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT")

# Send a completion call to generate an answer
print("Sending a test completion job")
start_phrase = "Tell me a joke"

response = client.completions.create(
    model=deployment_name, prompt=start_phrase, max_tokens=10
)
print(response)
