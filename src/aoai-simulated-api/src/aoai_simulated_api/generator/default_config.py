from typing import Callable
from fastapi import Request, Response


# This file contains a default implementation of the get_generators function
# You can configure your own generators by creating a generator_config.py file and setting the
# GENERATOR_CONFIG_PATH environment variable to the path of the file when running the API
# See src/examples/generator_config.py for an example of how to define your own generators


def get_generators(setup_context) -> list[Callable[[Request], Response | None]]:
    # Return a list of functions
    # If the function returns a Response object, it will be used as the response for the request
    # If the function returns None, the next function in the list will be called
    return [
        setup_context.built_in_generators["azure_openai_embedding"],
        setup_context.built_in_generators["azure_openai_completion"],
        setup_context.built_in_generators["azure_openai_chat_completion"],
        setup_context.built_in_generators["doc_intelligence_analyze"],
        setup_context.built_in_generators["doc_intelligence_analyze_result"],
        lambda context, request: Response(
            content="Default generated response - see src/examples/generator_config.py for example generator code",
            status_code=200,
        ),
    ]
