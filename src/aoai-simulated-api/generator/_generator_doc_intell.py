import datetime
import os
import uuid
from fastapi import Request, Response

# dictionary of submitted operations keyed on operation ID
operations = {}


async def generate_analyze_prebuilt_receipt(context, request: Request) -> Response | None:
    global operations
    is_match, _ = context.is_route_match(
        request=request, path="/formrecognizer/documentModels/prebuilt-receipt:analyze", methods=["POST"]
    )
    if not is_match:
        return None

    operation_id = str(uuid.uuid4())
    # Build the response header
    # TODO - get base address from config to allow for running in ACA/AKS/... (but default to localhost and current port)
    operation_location = f"http://localhost:8000/formrecognizer/documentModels/prebuilt-receipt/analyzeResults/{operation_id}?api-version=2023-07-31"

    # Set the HTTP response headers.
    headers = {"Operation-Location": operation_location}

    operations[operation_id] = "TODO"  # replace this with any info required for generating the response

    # Return the response
    return Response(status_code=202, headers=headers)


async def generate_analyze_receipt_result(context, request: Request) -> Response | None:
    global operations
    is_match, path_params = context.is_route_match(
        request=request,
        path="/formrecognizer/documentModels/prebuilt-receipt/analyzeResults/{operation_id}",
        methods=["GET"],
    )
    if not is_match:
        return None

    operation_id = path_params["operation_id"]
    operation = operations.get(operation_id)
    if not operation:
        return Response(status_code=404)
    del operations[operation_id]  # TODO - should we delete or leave to allow multiple queries of the result?

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
