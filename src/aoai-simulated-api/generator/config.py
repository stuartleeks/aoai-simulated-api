from typing import Callable
from fastapi import Request, Response

# This file contains a default implementation of the get_generators function
# You can configure your own generators by creating a generator_config.py file and setting the
# GENERATOR_CONFIG_PATH environment variable to the path of the file when running the API
# See src/examples/generator_config.py for an example of how to define your own generators


def get_generators() -> list[Callable[[Request], Response | None]]:
    # Return a list of functions
    # If the function returns a Response object, it will be used as the response for the request
    # If the function returns None, the next function in the list will be called
    return [
        lambda request: Response(
            content="Default generated response - see src/examples/generator_config.py for example generator code",
            status_code=200,
        ),
    ]
