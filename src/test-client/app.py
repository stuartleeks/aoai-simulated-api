import os
from openai import AzureOpenAI


api_key = os.getenv("AZURE_OPENAI_KEY")
api_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
# This will correspond to the custom name you chose for your deployment when you deployed a model. Use a gpt-35-turbo-instruct deployment.
deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT")

mode = os.getenv("MODE")

if api_key is None:
    print("AZURE_OPENAI_KEY is not set")
    exit(1)
if api_endpoint is None:
    print("AZURE_OPENAI_ENDPOINT is not set")
    exit(1)
if deployment_name is None:
    print("AZURE_OPENAI_DEPLOYMENT is not set")
    exit(1)

mode_options = ["completion", "chat", "chatbot"]

if mode is None:
    print(f"MODE is not set - defaulting to completion. Options are {mode_options}")
    mode = "completion"

print("Connecting to: " + api_endpoint)
client = AzureOpenAI(
    api_key=api_key, api_version="2023-12-01-preview", azure_endpoint=api_endpoint
)
print("")


def send_test_completion():
    # Send a completion call to generate an answer
    print("Sending a test completion job")
    response = client.completions.create(
        model=deployment_name, prompt="A good DAD joke is ....", max_tokens=10
    )
    print(response)

    print("")
    print("Sending another test completion job")
    response = client.completions.create(
        model=deployment_name, prompt="A good story opening is!", max_tokens=10
    )
    print(response)


def send_test_chat_completion():
    response = client.chat.completions.create(
        model=deployment_name,
        messages=[{"role": "user", "content": "What is the meaning of life?"}],
    )
    print(response)


def chat_bot():
    messages = []
    while True:
        user_input = input("\x1b[0;32mYou: ")
        if not user_input:
            break
        messages.append({"role": "user", "content": user_input})
        response = client.chat.completions.create(
            model=deployment_name, messages=messages
        )
        print("\x1b[0;33mBot: " + response.choices[0].message.content)
        print("\x1b[0m")


if mode == "completion":
    send_test_completion()
elif mode == "chat":
    send_test_chat_completion()
elif mode == "chatbot":
    chat_bot()
