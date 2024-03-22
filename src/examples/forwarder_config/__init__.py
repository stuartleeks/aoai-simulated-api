import json
import logging
import os
from typing import Callable
from aoai_simulated_api.pipeline import RequestContext
import fastapi
from fastapi.datastructures import URL
import requests

from forwarder_config.document_intelligence import forward_to_azure_document_intelligence

# This file is an example of how you can define your request forwarders
# Forwarders can be sync or async methods


def get_forwarders() -> list[Callable[[RequestContext], fastapi.Response | requests.Response | dict | None]]:
    # Return a list of functions to call when recording and no matching saved request is found
    # If the function returns a Response object (from FastAPI or requests package), it will be used as the response for the request
    # If the function returns a dict then it should have a "response" property with the response and a "persist" property that is True/False to indicate whether to persist the response
    # If the function returns None, the next function in the list will be called
    return [
        forward_to_azure_document_intelligence,
    ]
