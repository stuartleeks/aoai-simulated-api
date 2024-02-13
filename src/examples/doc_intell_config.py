import datetime
import os
from fastapi import Request, Response

# TODO: Is this a good approach? Not sure if this is the best way.
OPERATION_ID = "0f3f83f2-0014-4d20-adcf-8268399e4ea7"


async def generate_analyze_prebuilt_receipt(request: Request) -> Response | None:
    if request.url.path != "/formrecognizer/documentModels/prebuilt-receipt:analyze" or request.method != "POST":
        return None

    # Build the respons header
    operation_location = f"http://localhost:8000/formrecognizer/documentModels/prebuilt-receipt/analyzeResults/{OPERATION_ID}?api-version=2023-07-31"

    # Set the HTTP response headers.
    headers = {"Operation-Location": operation_location}

    # Return the response
    return Response(status_code=202, headers=headers)


async def generate_analyze_receipt_result(request: Request) -> Response | None:
    if (
        request.url.path != f"/formrecognizer/documentModels/prebuilt-receipt/analyzeResults/{OPERATION_ID}"
        or request.method != "GET"
    ):
        return None

    # Load the result from a file
    base_path = os.path.dirname(os.path.realpath(__file__))
    receipt_path = os.path.join(base_path, "analyze-receipt-result.json")

    with open(receipt_path, "r") as f:
        content = f.read()

    # Set the HTTP response headers.
    headers = {
        "Content-Length": f"{len(content)}",
        "Content-Type": "application/json; charset=utf-8",
    }

    # Return the response.
    return Response(status_code=200, content=content, headers=headers)


def get_generators() -> list:
    return [generate_analyze_prebuilt_receipt, generate_analyze_receipt_result]
