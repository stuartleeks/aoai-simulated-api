from fastapi import Request, Response

async def generate_echo_response(context, request: Request) -> Response | None:
    if request.url.path != "/echo" or request.method != "POST":
        return None
    request_body = await request.body()
    return Response(content=f"Echo (temp.py): {request_body.decode("utf-8")}", status_code=200)
