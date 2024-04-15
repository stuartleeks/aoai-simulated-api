from fastapi import Request


def hash_request_parts(method: str, url: str, body: bytes):
    # Potential future optimisation would be to look for incremental hashing function in Python
    body_hash = hash(body)
    return hash(method + "|" + url + "|" + str(body_hash))


async def get_request_hash(request: Request):
    body = await request.body()
    return hash_request_parts(request.method, request.url.path, body)
