from fastapi import Request, Response
from starlette.routing import Route, Match
from ._generator_openai import azure_openai_embedding, azure_openai_completion, azure_openai_chat_completion
from ._generator_doc_intell import doc_intelligence_analyze, doc_intelligence_analyze_result


# re-using Starlette's Route class to define a route
# endpoint to pass to Route
def _endpoint():
    pass


class GeneratorSetupContext:

    def __init__(self) -> None:
        self.built_in_generators = {
            "azure_openai_embedding": azure_openai_embedding,
            "azure_openai_completion": azure_openai_completion,
            "azure_openai_chat_completion": azure_openai_chat_completion,
            "doc_intelligence_analyze": doc_intelligence_analyze,
            "doc_intelligence_analyze_result": doc_intelligence_analyze_result,
        }


class GeneratorCallContext:
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
        path_to_match = GeneratorCallContext._strip_path_query(request.url.path)
        match, scopes = route.matches({"type": "http", "method": request.method, "path": path_to_match})
        if match != Match.FULL:
            return (False, {})
        return (True, scopes["path_params"])
