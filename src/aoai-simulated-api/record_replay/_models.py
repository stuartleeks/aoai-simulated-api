from dataclasses import dataclass


@dataclass
class RecordedResponse:
    request_hash: int
    status_code: int
    status_message: str
    headers: dict[str, list[str]]
    body: str
    # full_request currently here for compatibility with VCR serialization format
    # it _is_ handy for human inspection to have the URL/body etc. in the recording
    full_request: dict
