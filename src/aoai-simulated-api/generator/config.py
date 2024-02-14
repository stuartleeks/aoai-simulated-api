from asyncio import sleep
from fastapi import Request, Response
from starlette.routing import Route
from typing import Callable

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


async def azure_open_ai_completion(context, request: Request) -> Response | None:
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


def get_generators() -> list[Callable[[Request], Response | None]]:
    # Return a list of functions
    # If the function returns a Response object, it will be used as the response for the request
    # If the function returns None, the next function in the list will be called
    return [
        azure_open_ai_completion,
        lambda context, request: Response(
            content="Default generated response - see src/examples/generator_config.py for example generator code",
            status_code=200,
        ),
    ]
