from dataclasses import dataclass
from typing import Awaitable, Callable

# from aoai_simulated_api.pipeline import RequestContext
from fastapi import Request, Response
from requests import Response as requests_Response
from starlette.routing import Route, Match


class RequestContext:
    _config: "Config"
    _request: Request
    _values: dict[str, any]

    def __init__(self, config: "Config", request: Request):
        self._config = config
        self._request = request
        self._values = {}

    @property
    def config(self) -> "Config":
        return self._config

    @property
    def request(self) -> Request:
        return self._request

    @property
    def values(self) -> dict[str, any]:
        return self._values

    def _strip_path_query(self, path: str) -> str:
        query_start = path.find("?")
        if query_start != -1:
            path = path[:query_start]
        return path

    def is_route_match(self, request: Request, path: str, methods: list[str]) -> tuple[bool, dict]:
        """
        Checks if a given route matches the provided request.

        Args:
                route (Route): The route to check against.
                request (Request): The request to match.

        Returns:
                tuple[bool, dict]: A tuple containing a boolean indicating whether the route matches the request,
                and a dictionary of path parameters if the match is successful.
        """

        # TODO - would a FastAPI router simplify this?

        route = Route(path=path, methods=methods, endpoint=_endpoint)
        path_to_match = self._strip_path_query(request.url.path)
        match, scopes = route.matches({"type": "http", "method": request.method, "path": path_to_match})
        if match != Match.FULL:
            return (False, {})
        return (True, scopes["path_params"])


@dataclass
class RecordingConfig:
    dir: str
    autosave: bool
    aoai_api_key: str | None = None
    aoai_api_endpoint: str | None = None
    forwarders: (
        list[
            Callable[
                [RequestContext],
                Response
                | Awaitable[Response]
                | requests_Response
                | Awaitable[requests_Response]
                | dict
                | Awaitable[dict]
                | None,
            ]
        ]
        | None
    ) = None


@dataclass
class Config:
    """
    Configuration for the simulator
    """

    simulator_mode: str
    simulator_api_key: str
    recording: RecordingConfig
    openai_deployments: dict[str, "OpenAIDeployment"] | None
    generators: list[Callable[[RequestContext], Response | Awaitable[Response] | None]]
    doc_intelligence_rps: int


@dataclass
class OpenAIDeployment:
    name: str
    model: str
    tokens_per_minute: int


# re-using Starlette's Route class to define a route
# endpoint to pass to Route
def _endpoint():
    pass
