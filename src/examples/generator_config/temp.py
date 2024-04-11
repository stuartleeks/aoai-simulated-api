from aoai_simulated_api.pipeline import RequestContext
from fastapi import Response

async def generate_echo_response(context: RequestContext) -> Response | None:
    request = context.request
    if request.url.path != "/echo" or request.method != "POST":
        return None
    request_body = await request.body()
    return Response(content=f"Echo (temp.py): {request_body.decode("utf-8")}", status_code=200)
