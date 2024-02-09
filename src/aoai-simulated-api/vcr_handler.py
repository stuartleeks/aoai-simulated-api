from dataclasses import dataclass
import requests
import vcr
from fastapi import Request, Response

vcr_filtered_request_headers = [
    # ignore api-key and don't persist!
    "api-key",
    # ignore these headers to reduce noise
    "user-agent",
    "x-stainless-arch",
    "x-stainless-async",
    "x-stainless-lang",
    "x-stainless-os",
    "x-stainless-package-version",
    "x-stainless-runtime",
    "x-stainless-runtime-version",
    "connection",
    "Content-Length",
    "accept-encoding",
]

var_filtered_response_headers = [
    # TODO - which (if any) of these do we care about? Any that we want to include in the responses?
    "apim-request-id",
    "azureml-model-session",
    "x-accel-buffering",
    "x-content-type-options",
    "x-ms-client-request-id",
    "x-ms-region",
    "x-request-id",
    "Cache-Control",
    "Content-Length",
    "Date",
    "Strict-Transport-Security",
    "access-control-allow-origin",
    # "x-ratelimit-remaining-requests",
    # "x-ratelimit-remaining-tokens",
]


class VcrHandler:
    def __init__(
        self,
        simulator_mode: str,
        api_endpoint: str,
        api_key: str,
        recording_dir: str,
        recording_format: str = "yaml",
    ):
        self.simulator_mode = simulator_mode
        self.api_endpoint = api_endpoint
        self.api_key = api_key
        self.recording_dir = recording_dir
        self.recording_format = recording_format

    def _before_record_response(response):
        for header in var_filtered_response_headers:
            if response["headers"].get(header):
                del response["headers"][header]
        return response

    def _get_cassette_name(self, request: Request):
        return request.url.path.strip("/").replace("/", "_") + "." + self.recording_format

    async def handle_request_with_vcr(self, request: Request) -> Response:
        # https://vcrpy.readthedocs.io/en/latest/usage.html#record-modes
        if self.simulator_mode == "record":
            # add new requests but replay existing ones - can delete the file to start over
            record_mode = "new_episodes"
        elif self.simulator_mode == "replay":
            # don't record new requests, only replay existing ones
            record_mode = "none"
        else:
            raise NotImplementedError(f"simulator mode not implemented: '{self.simulator_mode}'")

        try:
            # TODO - explore caching the vcr instance. Does this help as the cassette file gets larger?
            my_vcr = vcr.VCR(
                before_record_response=VcrHandler._before_record_response,
                filter_headers=vcr_filtered_request_headers,
                record_mode=record_mode,
                cassette_library_dir=self.recording_dir,
                serializer=self.recording_format,
                # https://vcrpy.readthedocs.io/en/latest/configuration.html#request-matching
                match_on=["uri", "method", "body"],
            )
            with my_vcr.use_cassette(self._get_cassette_name(request)):
                # create new HTTP request to api_endpoint. copy headers, body, etc from request
                url = self.api_endpoint
                if url.endswith("/"):
                    url = url[:-1]
                url += request.url.path + "?" + request.url.query

                # Copy most headers, but override auth
                fwd_headers = {k: v for k, v in request.headers.items() if k not in ["host", "authorization"]}
                fwd_headers["api-key"] = self.api_key

                body = await request.body()

                fwd_response = requests.request(
                    request.method,
                    url,
                    headers=fwd_headers,
                    data=body,
                )

                # TODO - what customisation do we want to apply? Overriding tokens remaining etc?
                response = Response(
                    fwd_response.text,
                    status_code=fwd_response.status_code,
                    headers={k: v for k, v in fwd_response.headers.items()},
                )
                return response
        except vcr.errors.CannotOverwriteExistingCassetteException as e:
            print(f"Cannot overwrite existing recording (simulator_mode={self.simulator_mode}): {e}", flush=True)
            return Response(status_code=500, content=str(e))
