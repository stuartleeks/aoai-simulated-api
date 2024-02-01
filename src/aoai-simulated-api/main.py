import httpx
import os
from fastapi import FastAPI, Request

api_key = os.getenv("AZURE_OPENAI_KEY")
api_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")

if api_key is None:
    print("AZURE_OPENAI_KEY is not set", flush=True)
    exit(1)

if api_endpoint is None:
    print("AZURE_OPENAI_ENDPOINT is not set", flush=True)
    exit(1)

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "👋 aoai-simulated-api is running"}


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def catchall(request: Request):
    print("⚠️ unhandled route: " + request.url.path, flush=True)
    body = await request.body()

    fwd_headers = { k: v for k, v in request.headers.items() if k not in ["host", "authorization"]}
    fwd_headers["api-key"] = api_key

    # create new HTTP request to api_endpoint. copy headers, body, etc from request
    async with httpx.AsyncClient() as client:
        url = api_endpoint
        if url.endswith("/"):
            url = url[:-1]
        url += request.url.path + "?" + request.url.query
        print("Forwarding to: " + url, flush=True)
        print("Forwarding headers: " + str(fwd_headers), flush=True)
        
        response = await client.request(
            request.method,
            url,
            headers=fwd_headers,
            data=body
        )
        print(f"Response ({response.status_code}):", flush=True)
        print(response.headers, flush=True)
        print(response.text, flush=True)
        
        # TODO set headers, status code, etc?
        return response.text


