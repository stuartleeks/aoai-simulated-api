from fastapi import Request, Response

from generator_config.temp import generate_echo_response

# This file is an example of how you can define your generators
# Generators can be sync or async methods

# async def generate_echo_response(context, request: Request) -> Response | None:
#     if request.url.path != "/echo" or request.method != "POST":
#         return None
#     request_body = await request.body()
#     return Response(content=f"Echo: {request_body.decode("utf-8")}", status_code=200)


def get_generators(context) -> list:
    return [generate_echo_response]
