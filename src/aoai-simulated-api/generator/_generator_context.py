from fastapi import Request, Response
from starlette.routing import Route, Match


# re-using Starlette's Route class to define a route
# endpoint to pass to Route
def _endpoint():
    pass


class GeneratorContext:
    def _strip_path_query(path: str) -> str:
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
        match, scopes = route.matches(
            {"type": "http", "method": request.method, "path": GeneratorContext._strip_path_query(request.url.path)}
        )
        if match != Match.FULL:
            return (False, {})
        return (True, scopes["path_params"])
