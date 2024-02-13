import importlib.util
import inspect
from fastapi import Request, Response
from requests import Response as requests_Response


class ForwardedResponse:
    def __init__(self, response: Response, persist_response: bool):
        self.response = response
        self.persist_response = persist_response


def _load_forwarders(generator_config_path: str):
    module_spec = importlib.util.spec_from_file_location("__forwarders_module", generator_config_path)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module.get_forwarders()


class RequestForwarder:
    def __init__(self, forwarder_config_path: str):
        self._forwarders = _load_forwarders(forwarder_config_path)

    async def forward_request(self, request: Request) -> ForwardedResponse:
        for generator in self._forwarders:
            response = generator(request)
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
                    raise Exception(f"Unhandled response type from forwarder: {type(response)}")

                if "Content-Length" in response.headers.keys():
                    # Content-Length will automatically be set when we return
                    # Strip out before recording to avoid issues
                    del response.headers["Content-Length"]

                # wrap and return
                return ForwardedResponse(response=response, persist_response=persist_response)

        return None
