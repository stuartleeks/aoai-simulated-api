# This file is an example of how you can define your generators
# Generators can be sync or async methods


from aoai_simulated_api.models import Config, RequestContext
from aoai_simulated_api.generator.openai import (
    create_lorem_chat_completion_response,
    get_model_name_from_deployment_name,
)
from fastapi import Response


def initialize(config: Config):
    """initialize is the entry point invoked by the simulator"""

    # replace the default azure_openai_chat_completion generator with this custom one

    # iterate through the generators to find the default azure_openai_chat_completion generator

    default_generator_index = -1
    for index, generator in enumerate(config.generators):
        if generator.__name__ == "azure_openai_chat_completion":
            default_generator_index = index
            break
    if default_generator_index == -1:
        raise ValueError("azure_openai_chat_completion generator not found in the config")

    config.generators[default_generator_index] = custom_azure_openai_chat_completion


async def custom_azure_openai_chat_completion(context: RequestContext) -> Response | None:
    """
    Custom generator for OpenAI chat completions that only generates a single word response and sets the finish_reason to "stop"
    """
    request = context.request
    is_match, path_params = context.is_route_match(
        request=request, path="/openai/deployments/{deployment}/chat/completions", methods=["POST"]
    )
    if not is_match:
        return None

    request_body = await request.json()
    deployment_name = path_params["deployment"]
    model_name = get_model_name_from_deployment_name(context, deployment_name)
    messages = request_body["messages"]

    # Here we fix the number of words to generate to 1 and set the finish_reason to "stop".
    # In a more realistic extension you would add logic to tailor the response sizes
    # or finish_reason based on the input messages observed in your system.
    words_to_generate = 1
    finish_reason = "stop"

    streaming = request_body.get("stream", False)
    return create_lorem_chat_completion_response(
        context=context,
        deployment_name=deployment_name,
        model_name=model_name,
        streaming=streaming,
        words_to_generate=words_to_generate,
        prompt_messages=messages,
        finish_reason=finish_reason,
    )
