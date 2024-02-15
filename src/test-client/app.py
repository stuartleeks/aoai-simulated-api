import os
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient

aoai_modes = [
    "completion",
    "chat",
    "chatbot",
    "chatbot-stream",
]
mode_options = aoai_modes + ["doc-intelligence"]

mode = os.getenv("MODE")
if mode is None:
    print(f"MODE is not set - defaulting to completion. Options are {mode_options}")
    mode = "completion"


if mode in aoai_modes:
    api_key = os.getenv("AZURE_OPENAI_KEY")
    api_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    # This will correspond to the custom name you chose for your deployment when you deployed a model. Use a gpt-35-turbo-instruct deployment.
    deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT")

    if api_key is None:
        print("AZURE_OPENAI_KEY is not set")
        exit(1)
    if api_endpoint is None:
        print("AZURE_OPENAI_ENDPOINT is not set")
        exit(1)
    if deployment_name is None:
        print("AZURE_OPENAI_DEPLOYMENT is not set")
        exit(1)

    print("Connecting to: " + api_endpoint)
    aoai_client = AzureOpenAI(
        api_key=api_key, api_version="2023-12-01-preview", azure_endpoint=api_endpoint, max_retries=0
    )
    print("")

if mode == "doc-intelligence":
    api_endpoint = os.environ["AZURE_FORM_RECOGNIZER_ENDPOINT"]
    api_key = os.environ["AZURE_FORM_RECOGNIZER_KEY"]

    credential = AzureKeyCredential(api_key)
    document_analysis_client = DocumentAnalysisClient(api_endpoint, credential)


def send_test_completion():
    # Send a completion call to generate an answer
    prompt_1 = "A good DAD joke is ...."
    print("Sending a test completion job: ", prompt_1)
    response = aoai_client.completions.create(model=deployment_name, prompt=prompt_1, max_tokens=50)
    print(response.choices[0].text)

    print("")
    prompt_2 = "A good story opening is"
    print("Sending another test completion job: ", prompt_2)
    response = aoai_client.completions.create(model=deployment_name, prompt=prompt_2, max_tokens=50)
    print(response.choices[0].text)


def send_test_chat_completion():
    response = aoai_client.chat.completions.create(
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
        response = aoai_client.chat.completions.create(model=deployment_name, messages=messages)
        response_content = response.choices[0].message.content
        messages.append({"role": "assistant", "content": response_content})
        print("\x1b[0;33mBot: " + response_content)
        print("\x1b[0m")


def chat_bot_stream():
    messages = []
    while True:
        user_input = input("\x1b[0;32mYou: ")
        if not user_input:
            break
        messages.append({"role": "user", "content": user_input})
        response = aoai_client.chat.completions.create(model=deployment_name, messages=messages, stream=True)
        print("\x1b[0;33mBot: ", end="")
        bot_response = ""
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                delta_content = chunk.choices[0].delta.content
                bot_response += delta_content
                print(delta_content, end="", flush=True)
        messages.append({"role": "assistant", "content": bot_response})
        print("\x1b[0m")


def doc_intelligence():
    base_path = os.path.dirname(os.path.realpath(__file__))
    pdf_path = os.path.join(base_path, "receipt.png")

    with open(pdf_path, "rb") as f:
        poller = document_analysis_client.begin_analyze_document("prebuilt-receipt", f)

    result = poller.result()
    print("Poller result: ", result)


if mode == "completion":
    send_test_completion()
elif mode == "chat":
    send_test_chat_completion()
elif mode == "chatbot":
    chat_bot()
elif mode == "chatbot-stream":
    chat_bot_stream()
elif mode == "doc-intelligence":
    doc_intelligence()
else:
    print("No matching mode found: " + mode)
