from fastapi import Request, Response

# This file is an example of how you can define your generators
# Generators can be sync or async methods

async def generate_echo_response(request: Request) -> Response | None:
    if request.url.path != "/echo" or request.method != "POST":
        return None
    request_body = await request.body()
    return Response(content=f"Echo: {request_body.decode("utf-8")}", status_code=200)


def get_generators() -> list:
    return [generate_echo_response]
