# This file is an example of how you can define your generators
# Generators can be sync or async methods


from aoai_simulated_api.models import Config, RequestContext
from fastapi import Response

def initialize(config: Config):
    """initialize is the entry point invoked by the simulator"""
    config.generators.append(generate_echo_response)

async def generate_echo_response(context: RequestContext) -> Response | None:
    request = context.request
    if request.url.path != "/echo" or request.method != "POST":
        return None
    request_body = await request.body()
    return Response(content=f"Echo: {request_body.decode("utf-8")}", status_code=200)

