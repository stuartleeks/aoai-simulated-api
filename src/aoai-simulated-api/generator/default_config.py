from asyncio import sleep
from fastapi import Request, Response
from typing import Callable
from ._generator_openai import azure_open_ai_completion
from ._generator_doc_intell import generate_analyze_prebuilt_receipt, generate_analyze_receipt_result

import json
import lorem
import nanoid
import tiktoken
import time

# This file contains a default implementation of the get_generators function
# You can configure your own generators by creating a generator_config.py file and setting the
# GENERATOR_CONFIG_PATH environment variable to the path of the file when running the API
# See src/examples/generator_config.py for an example of how to define your own generators


def get_generators() -> list[Callable[[Request], Response | None]]:
    # Return a list of functions
    # If the function returns a Response object, it will be used as the response for the request
    # If the function returns None, the next function in the list will be called
    return [
        azure_open_ai_completion,
        generate_analyze_prebuilt_receipt,
        generate_analyze_receipt_result,
        lambda context, request: Response(
            content="Default generated response - see src/examples/generator_config.py for example generator code",
            status_code=200,
        ),
    ]
