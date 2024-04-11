import importlib.util
import inspect
import os
import sys
from typing import Callable
from aoai_simulated_api.pipeline import RequestContext
from fastapi import Response
from requests import Response as requests_Response


class ForwardedResponse:
    def __init__(self, response: Response, persist_response: bool):
        self.response = response
        self.persist_response = persist_response


def _load_forwarders(forwarder_config_path: str):
    # forwarder_config_path is the path to a folder with a __init__.py
    # use the last folder name as the module name as that is intuitive when the __init__.py
    # references other files in the same folder
    config_is_dir = os.path.isdir(forwarder_config_path)
    if config_is_dir:
        module_name = os.path.basename(forwarder_config_path)
        path_to_load = os.path.join(forwarder_config_path, "__init__.py")
    else:
        module_name = "__forwarder_config"
        path_to_load = forwarder_config_path

    module_spec = importlib.util.spec_from_file_location(module_name, path_to_load)
    module = importlib.util.module_from_spec(module_spec)
    sys.modules[module_spec.name] = module
    module_spec.loader.exec_module(module)
    return module.get_forwarders()


def create_forwarder(forwarder_config_path: str) -> Callable[[RequestContext], ForwardedResponse]:

    forwarders = _load_forwarders(forwarder_config_path)

    async def forward_request(context: RequestContext) -> ForwardedResponse:
        for forwarder in forwarders:
            response = forwarder(context)
            if response is not None and inspect.isawaitable(response):
                response = await response
            if response is not None:
                persist_response = True
                # unwrap dictionary response
                if isinstance(response, dict):
                    original_response = response
                    response = original_response["response"]
                    persist_response = original_response.get("persist", persist_response)

                # normalize response to FastAPI Response
                if isinstance(response, Response):
                    # Already a FastAPI response
                    pass
                elif isinstance(response, requests_Response):
                    # convert requests response to FastAPI response
                    response = Response(
                        content=response.text, status_code=response.status_code, headers=response.headers
                    )
                else:
                    raise ValueError(f"Unhandled response type from forwarder: {type(response)}")

                if "Content-Length" in response.headers.keys():
                    # Content-Length will automatically be set when we return
                    # Strip out before recording to avoid issues
                    del response.headers["Content-Length"]

                # wrap and return
                return ForwardedResponse(response=response, persist_response=persist_response)

        return None

    return forward_request
