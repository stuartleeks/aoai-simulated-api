from fastapi import Request, Response

import json
import lorem
import nanoid
import tiktoken
import time

# This file contains a default implementation of the get_generators function
# You can configure your own generators by creating a generator_config.py file and setting the
# GENERATOR_CONFIG_PATH environment variable to the path of the file when running the API
# See src/examples/generator_config.py for an example of how to define your own generators


# 0.72 is based on generating a bunch of lorem ipsum and counting the tokens
# This was for a gpt-3.5 model
TOKEN_TO_WORD_FACTOR = 0.72
tiktoken_encoding = tiktoken.encoding_for_model("gpt-3.5")

# API docs: https://learn.microsoft.com/en-gb/azure/ai-services/openai/reference


async def azure_openai_completion(context, request: Request) -> Response | None:
    is_match, path_params = context.is_route_match(
        request=request, path="/openai/deployments/{deployment}/completions", methods=["POST"]
    )
    if not is_match:
        return None

    # TODO - Use name convention to find the tiktoken model from deployment_name
    deployment_name = path_params["deployment"]
    request_body = await request.json()
    prompt_tokens = len(tiktoken_encoding.encode(request_body["prompt"]))
    max_tokens = request_body.get("max_tokens", 10)  # TODO - what is the default max tokens?

    words_to_generate = int(TOKEN_TO_WORD_FACTOR * max_tokens)
    text = "".join(lorem.get_word(count=words_to_generate))

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
            "completion_tokens": max_tokens,
            "total_tokens": prompt_tokens + max_tokens,
        },
    }

    return Response(content=json.dumps(response_body), headers={"Content-Type": "application/json"}, status_code=200)


async def azure_openai_chat_completion(context, request: Request) -> Response | None:
    is_match, path_params = context.is_route_match(
        request=request, path="/openai/deployments/{deployment}/chat/completions", methods=["POST"]
    )
    if not is_match:
        return None

    # TODO - determine the token size to use
    max_tokens = 250
    words_to_generate = int(TOKEN_TO_WORD_FACTOR * max_tokens)
    text = "".join(lorem.get_word(count=words_to_generate))

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
            "prompt_tokens": -1,  # TODO - calculate and fill out token usage
            "completion_tokens": -1,
            "total_tokens": -1,
        },
    }

    return Response(content=json.dumps(response_body), headers={"Content-Type": "application/json"}, status_code=200)
