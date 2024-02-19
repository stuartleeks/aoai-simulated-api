from fastapi import Request, Response

import json
import lorem
import nanoid
import tiktoken
import time


from constants import SIMULATOR_HEADER_OPENAI_TOKENS, SIMULATOR_HEADER_LIMITER, SIMULATOR_HEADER_LIMITER_KEY

# This file contains a default implementation of the get_generators function
# You can configure your own generators by creating a generator_config.py file and setting the
# GENERATOR_CONFIG_PATH environment variable to the path of the file when running the API
# See src/examples/generator_config.py for an example of how to define your own generators


# 0.72 is based on generating a bunch of lorem ipsum and counting the tokens
# This was for a gpt-3.5 model
TOKEN_TO_WORD_FACTOR = 0.72

# API docs: https://learn.microsoft.com/en-gb/azure/ai-services/openai/reference


def get_encoding_name_from_deployment_name(deployment_name: str) -> str:
    # TODO - Add config to map deployment name to the model name
    return "cl100k_base"


def get_model_name_from_deployment_name(deployment_name: str) -> str:
    # TODO - Add config to map deployment name to the model name
    return "gpt-3.5-turbo-0613"


# For details on the token counting, see https://cookbook.openai.com/examples/how_to_count_tokens_with_tiktoken


def num_tokens_from_string(string: str, encoding_name: str) -> int:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.get_encoding(encoding_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens


def num_tokens_from_messages(messages, model):
    """Return the number of tokens used by a list of messages."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        print("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")
    if model in {
        "gpt-3.5-turbo-0613",
        "gpt-3.5-turbo-16k-0613",
        "gpt-4-0314",
        "gpt-4-32k-0314",
        "gpt-4-0613",
        "gpt-4-32k-0613",
    }:
        tokens_per_message = 3
        tokens_per_name = 1
    elif model == "gpt-3.5-turbo-0301":
        tokens_per_message = 4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
        tokens_per_name = -1  # if there's a name, the role is omitted
    elif "gpt-3.5-turbo" in model:
        print("Warning: gpt-3.5-turbo may update over time. Returning num tokens assuming gpt-3.5-turbo-0613.")
        return num_tokens_from_messages(messages, model="gpt-3.5-turbo-0613")
    elif "gpt-4" in model:
        print("Warning: gpt-4 may update over time. Returning num tokens assuming gpt-4-0613.")
        return num_tokens_from_messages(messages, model="gpt-4-0613")
    else:
        raise NotImplementedError(
            f"""num_tokens_from_messages() is not implemented for model {model}. See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens."""
        )
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens


async def azure_openai_completion(context, request: Request) -> Response | None:
    is_match, path_params = context.is_route_match(
        request=request, path="/openai/deployments/{deployment}/completions", methods=["POST"]
    )
    if not is_match:
        return None

    # TODO - Use name convention to find the tiktoken model from deployment_name
    deployment_name = path_params["deployment"]
    encoding_name = get_encoding_name_from_deployment_name(deployment_name)
    request_body = await request.json()
    prompt_tokens = num_tokens_from_string(request_body["prompt"], encoding_name)
    max_tokens = request_body.get("max_tokens", 10)  # TODO - what is the default max tokens?

    words_to_generate = int(TOKEN_TO_WORD_FACTOR * max_tokens)
    text = "".join(lorem.get_word(count=words_to_generate))

    completion_tokens = num_tokens_from_string(text, encoding_name)
    total_tokens = prompt_tokens + completion_tokens

    response_body = {
        "id": "cmpl-" + nanoid.non_secure_generate(size=29),
        "object": "text_completion",
        "created": int(time.time()),
        "model": "gpt-35-turbo",  # TODO - parameterise
        "choices": [
            {
                "text": text,
                "index": 0,
                "finish_reason": "length",
                "logprobs": None,
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        },
    }

    return Response(
        content=json.dumps(response_body),
        headers={
            "Content-Type": "application/json",
            SIMULATOR_HEADER_OPENAI_TOKENS: str(total_tokens),
            SIMULATOR_HEADER_LIMITER: "openai",
            SIMULATOR_HEADER_LIMITER_KEY: deployment_name,
        },
        status_code=200,
    )


async def azure_openai_chat_completion(context, request: Request) -> Response | None:
    is_match, path_params = context.is_route_match(
        request=request, path="/openai/deployments/{deployment}/chat/completions", methods=["POST"]
    )
    if not is_match:
        return None

    request_body = await request.json()
    deployment_name = path_params["deployment"]
    encoding_name = get_encoding_name_from_deployment_name(deployment_name)
    model_name = get_model_name_from_deployment_name(deployment_name)
    prompt_tokens = num_tokens_from_messages(request_body["messages"], model_name)

    # TODO - determine the token size to use
    max_tokens = 250
    words_to_generate = int(TOKEN_TO_WORD_FACTOR * max_tokens)
    text = "".join(lorem.get_word(count=words_to_generate))
    completion_tokens = num_tokens_from_string(text, encoding_name)
    total_tokens = prompt_tokens + completion_tokens

    response_body = {
        "id": "chatcmpl-" + nanoid.non_secure_generate(size=29),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "gpt-35-turbo",  # TODO - parameterise
        "prompt_filter_results": [
            {
                "prompt_index": 0,
                "content_filter_results": {
                    "hate": {"filtered": False, "severity": "safe"},
                    "self_harm": {"filtered": False, "severity": "safe"},
                    "sexual": {"filtered": False, "severity": "safe"},
                    "violence": {"filtered": False, "severity": "safe"},
                },
            }
        ],
        "choices": [
            {
                "finish_reason": "stop",
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": text,
                },
                "content_filter_results": {
                    "hate": {"filtered": False, "severity": "safe"},
                    "self_harm": {"filtered": False, "severity": "safe"},
                    "sexual": {"filtered": False, "severity": "safe"},
                    "violence": {"filtered": False, "severity": "safe"},
                },
            },
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,  # TODO - calculate and fill out token usage
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        },
    }

    return Response(
        content=json.dumps(response_body),
        headers={
            "Content-Type": "application/json",
            SIMULATOR_HEADER_OPENAI_TOKENS: str(total_tokens),
            SIMULATOR_HEADER_LIMITER: "openai",
            SIMULATOR_HEADER_LIMITER_KEY: deployment_name,
        },
        status_code=200,
    )
