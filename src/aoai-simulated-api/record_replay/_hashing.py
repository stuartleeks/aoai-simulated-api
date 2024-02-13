from fastapi import Request


def hash_request_parts(method: str, url: str, body: bytes):
    body_hash = hash(body)  # TODO: look for incremental hashing function in Python
    return hash(method + "|" + url + "|" + str(body_hash))


async def get_request_hash(request: Request):
    body = await request.body()
    return hash_request_parts(request.method, request.url.path, body)
