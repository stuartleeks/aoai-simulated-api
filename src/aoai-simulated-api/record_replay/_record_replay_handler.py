import logging
import time
from fastapi import Request, Response


from ._hashing import get_request_hash, hash_request_parts
from ._models import RecordedResponse
from ._persistence import YamlRecordingPersister
from ._request_forwarder import RequestForwarder
from pipeline import RequestContext

logger = logging.getLogger(__name__)


class RecordReplayHandler:

    _recordings: dict[str, dict[int, RecordedResponse]]

    def __init__(
        self,
        simulator_mode: str,
        persister: YamlRecordingPersister,
        forwarder: RequestForwarder | None,
        autosave: bool,
    ):
        self._simulator_mode = simulator_mode
        self._persister = persister
        self._forwarder = forwarder
        self._autosave = autosave

        # recordings keyed by URL, within a recording, requests are keyed by hash of request values
        self._recordings = {}

    async def _get_recording_for_url(self, url: str) -> dict[int, RecordedResponse] | None:
        recording = self._recordings.get(url)
        if recording:
            return recording

        recording = self._persister.load_recording_for_url(url)
        if not recording:
            return None

        self._recordings[url] = recording
        return recording

    async def handle_request(self, context: RequestContext) -> Response | None:

        request = context.request
        url = request.url.path
        recording = await self._get_recording_for_url(url)
        if recording:
            request_hash = await get_request_hash(request)
            response_info = recording.get(request_hash)
            if response_info:
                headers = {k: v[0] for k, v in response_info.headers.items()}
                return Response(content=response_info.body, status_code=response_info.status_code, headers=headers)
            else:
                logger.debug(f"No recorded response found for request {request.method} {url}")
        else:
            logger.debug(f"No recording found for URL: {url}")

        if self._simulator_mode == "record":
            return await self._record_request(request)

        return None

    async def _record_request(self, request: Request) -> Response:
        if not self._forwarder:
            raise Exception("No forwarder available to record request")

        start_time = time.time()
        forwarded_response = await self._forwarder.forward_request(request)
        end_time = time.time()
        if not forwarded_response:
            raise Exception(
                f"Failed to forward request - no configured forwarders returned a response for {request.method} {request.url}"
            )
        elapsed_time = end_time - start_time
        elapsed_time_ms = int(elapsed_time * 1000)

        response = forwarded_response.response
        request_body = await request.body()
        body = response.body
        # limit the request headers we persist - avoid persisting secrets and keep recording size low
        allowed_request_headers = ["content-type", "accept"]
        request_headers = {k: [v] for k, v in request.headers.items() if k.lower() in allowed_request_headers}
        if "content-length" in response.headers:
            del response.headers["content-length"]

        text_content_types = ["application/json", "application/text"]  # TODO - handle other text types
        response_content_type = response.headers.get("content-type", "").split(";")[0]
        if response_content_type in text_content_types:
            # simplify format for editing recording files
            body = body.decode("utf-8")

        request_content_type = request.headers.get("content-type", "").split(";")[0]
        if request_content_type in text_content_types:
            request_body = request_body.decode("utf-8")

        recorded_response = RecordedResponse(
            status_code=response.status_code,
            headers={k: [v] for k, v in dict(response.headers).items()},
            body=body,
            request_hash=hash_request_parts(request.method, request.url.path, request_body),
            full_request={
                "method": request.method,
                "uri": str(request.url),
                "headers": request_headers,
                "body": request_body,
            },
            status_message="n/a",
            duration_ms=elapsed_time_ms,
        )

        if forwarded_response.persist_response:
            # Save the recording
            logger.info(f"📝 Storing recording for {request.method} {request.url}")
            recording = self._recordings.get(request.url.path)
            if not recording:
                recording = {}
                self._recordings[request.url.path] = recording
            recording[recorded_response.request_hash] = recorded_response

            if self._autosave:
                # Save the recording to disk
                self._persister.save_recording(request.url.path, recording)

        return Response(content=body, status_code=response.status_code, headers=response.headers)

    def save_recordings(self):
        for url in self._recordings.keys():
            self._persister.save_recording(url, self._recordings[url])
