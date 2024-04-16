import logging
import time
from typing import Callable
from fastapi import Response

from aoai_simulated_api import constants
from aoai_simulated_api.pipeline import RequestContext

from aoai_simulated_api.record_replay._hashing import get_request_hash, hash_request_parts
from aoai_simulated_api.record_replay._models import RecordedResponse
from aoai_simulated_api.record_replay._persistence import YamlRecordingPersister
from aoai_simulated_api.record_replay._request_forwarder import ForwardedResponse

logger = logging.getLogger(__name__)


class RecordReplayHandler:

    _recordings: dict[str, dict[int, RecordedResponse]]
    _forwarder: Callable[[RequestContext], ForwardedResponse] | None

    def __init__(
        self,
        simulator_mode: str,
        persister: YamlRecordingPersister,
        forwarder: Callable[[RequestContext], ForwardedResponse] | None,
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

        expect_recording_file = self._simulator_mode == "replay"
        recording = self._persister.load_recording_for_url(url, expect_recording_file)
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
                context.values[constants.RECORDED_DURATION_MS] = response_info.duration_ms
                return Response(content=response_info.body, status_code=response_info.status_code, headers=headers)
            else:
                logger.debug("No recorded response found for request %s %s", request.method, url)
        else:
            logger.debug("No recording found for URL: %s", url)

        if self._simulator_mode == "record":
            return await self._record_request(context)

        return None

    async def _record_request(self, context: RequestContext) -> Response:
        if not self._forwarder:
            raise ValueError("No forwarder available to record request")

        request = context.request

        start_time = time.time()
        forwarded_response: ForwardedResponse | None = await self._forwarder(context)
        end_time = time.time()
        if not forwarded_response:
            raise ValueError(
                "Failed to forward request - no configured forwarders returned a response for"
                + f"{request.method} {request.url}"
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

        text_content_types = ["application/json", "application/text"]
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
            logger.info("📝 Storing recording for %s %s", request.method, request.url)
            recording = self._recordings.get(request.url.path)
            if not recording:
                recording = {}
                self._recordings[request.url.path] = recording
            recording[recorded_response.request_hash] = recorded_response

            if self._autosave:
                # Save the recording to disk
                self._persister.save_recording(request.url.path, recording)

        context.values[constants.RECORDED_DURATION_MS] = elapsed_time_ms
        return Response(content=body, status_code=response.status_code, headers=response.headers)

    def save_recordings(self):
        for url, recording in self._recordings.items():
            self._persister.save_recording(url, recording)
