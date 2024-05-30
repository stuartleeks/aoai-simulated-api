import asyncio
import json
import logging
import time
import random

import lorem
import nanoid

from fastapi import Response
from fastapi.responses import StreamingResponse

from aoai_simulated_api.auth import validate_api_key_header
from aoai_simulated_api.models import RequestContext
from aoai_simulated_api.constants import (
    SIMULATOR_KEY_DEPLOYMENT_NAME,
    SIMULATOR_KEY_OPENAI_COMPLETION_TOKENS,
    SIMULATOR_KEY_OPENAI_TOTAL_TOKENS,
    SIMULATOR_KEY_LIMITER,
    SIMULATOR_KEY_OPERATION_NAME,
)
from aoai_simulated_api.generator.openai_tokens import num_tokens_from_string, num_tokens_from_messages

# This file contains a default implementation of the openai generators
# You can configure your own generators by creating a generator_config.py file and setting the
# EXTENSION_PATH environment variable to the path of the file when running the API
# See src/examples/generator_echo for an example of how to define your own generators

logger = logging.getLogger(__name__)

# 0.72 is based on generating a bunch of lorem ipsum and counting the tokens
# This was for a gpt-3.5 model
TOKEN_TO_WORD_FACTOR = 0.72

# API docs: https://learn.microsoft.com/en-gb/azure/ai-services/openai/reference

missing_deployment_names = set()

# pylint: disable-next=invalid-name
default_embedding_size = (
    1536  # text-embedding-3-small default (https://platform.openai.com/docs/guides/embeddings/what-are-embeddings)
)


def get_model_name_from_deployment_name(context: RequestContext, deployment_name: str) -> str:
    deployments = context.config.openai_deployments
    if deployments:
        deployment = deployments.get(deployment_name)
        if deployment:
            return deployment.model

    default_model = "gpt-3.5-turbo-0613"

    # Output warning for missing deployment name (only the first time we encounter it)
    if deployment_name not in missing_deployment_names:
        missing_deployment_names.add(deployment_name)
        logger.warning("Deployment %s not found in config, using default model %s", deployment_name, default_model)
    return default_model


def create_embedding_content(index: int, embedding_size=default_embedding_size):
    """Generates a random embedding"""
    return {
        "object": "embedding",
        "index": index,
        "embedding": [(random.random() - 0.5) * 4 for _ in range(embedding_size)],
    }


def create_embeddings_response(
    context: RequestContext, deployment_name: str, model_name: str, request_input: str | list
):
    embeddings = []
    if isinstance(request_input, str):
        tokens = num_tokens_from_string(request_input, model_name)
        embeddings.append(create_embedding_content(0))
    else:
        tokens = 0
        index = 0
        for i in request_input:
            tokens += num_tokens_from_string(i, model_name)
            embeddings.append(create_embedding_content(index))
            index += 1

    response_data = {
        "object": "list",
        "data": embeddings,
        "model": "ada",
        "usage": {"prompt_tokens": tokens, "total_tokens": tokens},
    }

    # store values in the context for use by the rate-limiter etc
    context.values[SIMULATOR_KEY_LIMITER] = "openai"
    context.values[SIMULATOR_KEY_OPERATION_NAME] = "embeddings"
    context.values[SIMULATOR_KEY_DEPLOYMENT_NAME] = deployment_name
    context.values[SIMULATOR_KEY_OPENAI_TOTAL_TOKENS] = tokens

    return Response(
        status_code=200,
        content=json.dumps(response_data),
        headers={
            "Content-Type": "application/json",
        },
    )


def create_completion_response(
    context: RequestContext,
    deployment_name: str,
    model_name: str,
    prompt_tokens: int,
    words_to_generate: int,
):
    """
    Creates a Response object for a completion request and sets context values for the rate-limiter etc
    """
    text = "".join(lorem.get_word(count=words_to_generate))

    completion_tokens = num_tokens_from_string(text, model_name)
    total_tokens = prompt_tokens + completion_tokens

    response_body = {
        "id": "cmpl-" + nanoid.non_secure_generate(size=29),
        "object": "text_completion",
        "created": int(time.time()),
        "model": model_name,
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

    # store values in the context for use by the rate-limiter etc
    context.values[SIMULATOR_KEY_LIMITER] = "openai"
    context.values[SIMULATOR_KEY_OPERATION_NAME] = "completions"
    context.values[SIMULATOR_KEY_DEPLOYMENT_NAME] = deployment_name
    context.values[SIMULATOR_KEY_OPENAI_COMPLETION_TOKENS] = completion_tokens
    context.values[SIMULATOR_KEY_OPENAI_TOTAL_TOKENS] = total_tokens

    return Response(
        content=json.dumps(response_body),
        headers={
            "Content-Type": "application/json",
        },
        status_code=200,
    )


def create_lorem_chat_completion_response(
    context: RequestContext,
    deployment_name: str,
    model_name: str,
    streaming: bool,
    words_to_generate: int,
    prompt_messages: list,
    finish_reason: str = "length",
):
    """
    Creates a Response object for a chat completion request by generating lorem ipsum text and sets context values for the rate-limiter etc.
    Handles streaming vs non-streaming
    """
    words = lorem.get_word(count=words_to_generate)
    return create_chat_completion_response(
        context=context,
        deployment_name=deployment_name,
        model_name=model_name,
        streaming=streaming,
        prompt_messages=prompt_messages,
        generated_content=words,
        finish_reason=finish_reason,
    )


def create_chat_completion_response(
    context: RequestContext,
    deployment_name: str,
    model_name: str,
    streaming: bool,
    prompt_messages: list,
    generated_content: list[str],
    finish_reason: str = "length",
):
    """
    Creates a Response object for a chat completion request and sets context values for the rate-limiter etc.
    Handles streaming vs non-streaming
    """

    prompt_tokens = num_tokens_from_messages(prompt_messages, model_name)

    if streaming:

        async def send_words():
            space = ""
            for word in generated_content.split(" "):
                chunk_string = json.dumps(
                    {
                        "id": "chatcmpl-" + nanoid.non_secure_generate(size=29),
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model_name": model_name,
                        "system_fingerprint": None,
                        "choices": [
                            {
                                "delta": {
                                    "content": space + word,
                                    "function_call": None,
                                    "role": None,
                                    "tool_calls": None,
                                    "finish_reason": None,
                                    "index": 0,
                                    "logprobs": None,
                                    "content_filter_results": {
                                        "hate": {"filtered": False, "severity": "safe"},
                                        "self_harm": {"filtered": False, "severity": "safe"},
                                        "sexual": {"filtered": False, "severity": "safe"},
                                        "violence": {"filtered": False, "severity": "safe"},
                                    },
                                },
                            },
                        ],
                    }
                )

                yield "data: " + chunk_string + "\n"
                yield "\n"
                await asyncio.sleep(0.05)
                space = " "

            chunk_string = json.dumps(
                {
                    "id": "chatcmpl-" + nanoid.non_secure_generate(size=29),
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model_name": model_name,
                    "system_fingerprint": None,
                    "choices": [
                        {
                            "delta": {
                                "content": None,
                                "function_call": None,
                                "role": None,
                                "tool_calls": None,
                                "finish_reason": finish_reason,
                                "index": 0,
                                "logprobs": None,
                                "content_filter_results": {
                                    "hate": {"filtered": False, "severity": "safe"},
                                    "self_harm": {"filtered": False, "severity": "safe"},
                                    "sexual": {"filtered": False, "severity": "safe"},
                                    "violence": {"filtered": False, "severity": "safe"},
                                },
                            },
                        },
                    ],
                }
            )

            yield "data: " + chunk_string + "\n"
            yield "\n"
            yield "[DONE]"

        return StreamingResponse(content=send_words())

    text = "".join(generated_content)
    completion_tokens = num_tokens_from_string(text, model_name)
    total_tokens = prompt_tokens + completion_tokens

    response_body = {
        "id": "chatcmpl-" + nanoid.non_secure_generate(size=29),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model_name,
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
                "finish_reason": finish_reason,
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
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        },
    }

    # store values in the context for use by the rate-limiter etc
    context.values[SIMULATOR_KEY_LIMITER] = "openai"
    context.values[SIMULATOR_KEY_OPERATION_NAME] = "chat-completions"
    context.values[SIMULATOR_KEY_DEPLOYMENT_NAME] = deployment_name
    context.values[SIMULATOR_KEY_OPENAI_COMPLETION_TOKENS] = completion_tokens
    context.values[SIMULATOR_KEY_OPENAI_TOTAL_TOKENS] = total_tokens

    return Response(
        content=json.dumps(response_body),
        headers={
            "Content-Type": "application/json",
        },
        status_code=200,
    )


def _validate_api_key_header(context: RequestContext):
    request = context.request
    validate_api_key_header(request=request, header_name="api-key", allowed_key_value=context.config.simulator_api_key)


async def azure_openai_embedding(context: RequestContext) -> Response | None:
    request = context.request
    is_match, path_params = context.is_route_match(
        request=request, path="/openai/deployments/{deployment}/embeddings", methods=["POST"]
    )
    if not is_match:
        return None

    _validate_api_key_header(context)

    deployment_name = path_params["deployment"]
    request_body = await request.json()
    model_name = get_model_name_from_deployment_name(context, deployment_name)
    request_input = request_body["input"]
    return create_embeddings_response(
        context=context,
        deployment_name=deployment_name,
        model_name=model_name,
        request_input=request_input,
    )


async def azure_openai_completion(context: RequestContext) -> Response | None:
    request = context.request
    is_match, path_params = context.is_route_match(
        request=request, path="/openai/deployments/{deployment}/completions", methods=["POST"]
    )
    if not is_match:
        return None

    _validate_api_key_header(context)

    deployment_name = path_params["deployment"]
    model_name = get_model_name_from_deployment_name(context, deployment_name)
    request_body = await request.json()
    prompt_tokens = num_tokens_from_string(request_body["prompt"], model_name)

    # TODO - determine the maxiumum tokens to use based on the model
    max_tokens = request_body.get("max_tokens", 4096)

    # TODO - randomise the finish reason (i.e. don't always use the full set of tokens)
    words_to_generate = int(TOKEN_TO_WORD_FACTOR * max_tokens)

    return create_completion_response(
        context=context,
        deployment_name=deployment_name,
        model_name=model_name,
        prompt_tokens=prompt_tokens,
        words_to_generate=words_to_generate,
    )


async def azure_openai_chat_completion(context: RequestContext) -> Response | None:
    request = context.request
    is_match, path_params = context.is_route_match(
        request=request, path="/openai/deployments/{deployment}/chat/completions", methods=["POST"]
    )
    if not is_match:
        return None

    _validate_api_key_header(context)

    request_body = await request.json()
    deployment_name = path_params["deployment"]
    model_name = get_model_name_from_deployment_name(context, deployment_name)
    messages = request_body["messages"]

    # TODO - determine the maxiumum tokens to use based on the model
    max_tokens = request_body.get("max_tokens", 4096)
    # TODO - randomise the finish reason (i.e. don't always use the full set of tokens)
    words_to_generate = int(TOKEN_TO_WORD_FACTOR * max_tokens)

    streaming = request_body.get("stream", False)
    return create_lorem_chat_completion_response(
        context=context,
        deployment_name=deployment_name,
        model_name=model_name,
        streaming=streaming,
        words_to_generate=words_to_generate,
        prompt_messages=messages,
    )
