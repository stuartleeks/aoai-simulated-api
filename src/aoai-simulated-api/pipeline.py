from fastapi import FastAPI, Request, Response


class RequestContext:
    _request: Request
    _values: dict[str, any]

    def __init__(self, request: Request):
        self._request = request
        self._values = {}

    @property
    def request(self) -> Request:
        return self._request

    @property
    def values(self) -> dict[str, any]:
        return self._values
