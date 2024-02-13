# aoai-simulated-api

This repo is an exploration into creating a simulated API implementation for Azure OpenAI (AOAI). This is a work in progress!

## Rationale

When building solutions using Azure OpenAI there are points in the development process where you may want to test your solution against a simulated API.

One example is working to integrate Open AI into your broader application. In this case you want to have representative responses to some known requests but don't need the "AI-ness" of the service (i.e. you don't need to be able to handle arbitrary user requests). A simulated API can provide these responses more cheaply and allow you an easy way to customise the responses to check different application behaviours.

Another example is load testing. In this case you are more likely to want to be able to submit a large number of requests with representative latency and rate-limiting, but don't need the actual AI responses.

## Overview

Currently, the simulated API has two approaches to simulating API responses: record/replay and generators.

With record/replay, the API can be run in record mode to act as a proxy between your application and Azure OpenAI, and it will record requests that are sent to it along with the corresponding response from OpenAI. Once recorded, the API can be run in replay mode to use the saved responses without forwarding to Azure OpenAI. The recordings are stored in YAML files which can be edited if you want to customise the responses.

The simulated API can also be run in generator mode, where responses are generated on the fly. This is useful for load testing scenarios where it would be costly/impractical to record the full set of responses.

The default generator is a simple example 

## Getting Started

This repo is configured with a Visual Studio Code [dev container](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) that sets up a Python environment ready to work in.

After cloning the repo, install dependencies using `make install-requirements`.

When running the simulated API, there are a number of environment variables to configure:

| Variable                  | Description                                                                                                                 |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `SIMULATOR_MODE`          | The mode the simulator should run in. Current options are `record`, `replay`, and `generate`.                               |
| `RECORDING_DIR`           | The directory to store the recorded requests and responses (defaults to `.recording`).                                      |
| `RECORDING_FORMAT`        | Currently only `yaml` is supported. Use to specify the format of the recorded requests/responses.                           |
| `RECORDING_AUTOSAVE`      | If set to `True` (default), the simulator will save the recording after each request.                                       |
| `GENERATOR_CONFIG_PATH`   | The path to a Python file that contains the generator configuration. See `src/examples/generator_config.py` for an example. |
| `FORWARDER_CONFIG_PATH`   | The path to a Python file that contains the forwarder configuration. See `src/examples/forwarder_config.py` for an example. |
| `AZURE_OPENAI_ENDPOINT`   | The endpoint for the Azure OpenAI service, e.g. `https://mysvc.openai.azure.com/`                                           |
| `AZURE_OPENAI_KEY`        | The API key for the Azure OpenAI service.                                                                                   |
| `AZURE_OPENAI_DEPLOYMENT` | The custom name of the model in your Azure OpenAI service. Use a gpt-35-turbo-instruct deployment.                          |

To run the simulated API, run `uvicorn main:app --reload --port 8000` from the `src/aoai-simulated-api` directory using the environment variables above to configure.

For example, to use the API in record/replay mode:

```bash
# Run the API in record mode
SIMULATOR_MODE=record AZURE_OPENAI_ENDPOINT=https://mysvc.openai.azure.com/ AZURE_OPENAI_KEY=your-api-key uvicorn main:app --reload --port 8000

# Run the API in replay mode
SIMULATOR_MODE=replay uvicorn main:app --reload --port 8000
```

To run the API in generator mode, you can set the `SIMULATOR_MODE` environment variable to `generate` and run the API as above.

```bash
# Run the API in generator mode
SIMULATOR_MODE=generate uvicorn main:app --reload --port 8000

# Run the API in generator mode with a custom generator configuration
# See src/examples/generator_config.py for an example of using a custom generator
SIMULATOR_MODE=generate GENERATOR_CONFIG_PATH=/path/to/generator_config.py uvicorn main:app --reload --port 8000
```

## Running in Docker

If you want to run the API simulator as a Docker container, there is a `Dockerfile` that can be used to build the image.

To build the image, run `docker build -t aoai-simulated-api .` from the `src/aoai-simulated-api` folder.

Once the image is built, you can run is using `docker run -p 8000:8000 -e SIMULATOR_MODE=record -e AZURE_OPENAI_ENDPOINT=https://mysvc.openai.azure.com/ -e AZURE_OPENAI_KEY=your-api-key aoai-simulated-api`.

Note that you can set any of the environment variable listed in the [Getting Started](#getting-started) section when running the container.
For example, if you have the recordings on your host (in `/some/path`) , you can mount that directory into the container using the `-v` flag: `docker run -p 8000:8000 -e SIMULATOR_MODE=replay -e RECORDING_DIR=/recording -v /some/path:/recording aoai-simulated-api`.

## Providing custom forwarders

When running in `record` mode, the simulator forwards requests on to a backend API and records the request/response information for later replay.

The default implementation uses the `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_KEY` environment variables to forward requests on to Azure OpenAI.

To provide a custom forwarder you need to:
1. create a Python file with a `get_forwarders` method
2. set the `FORWARDER_CONFIG_PATH` to point to your custom config when running the simulator


### Creating a custom forwarder

A custom forwarder file needs to have a `get_forwarders` method as shown below:

```python
from typing import Callable
from fastapi import Request
import requests

async def forward_to_my_host(request: Request) -> Response | None:
	# build up the forwarded request from the incoming request
	# you may need to modify the headers or other properties
	url = "<build up target url>"
    body = await request.body()
    response = requests.request(
        request.method,
        url,
        headers=request.headers,
        data=body,
    )
	return response


def get_forwarders() -> list[Callable[[fastapi.Request], fastapi.Response | requests.Response | dict | None]]:
    # Return a list of functions to call when recording and no matching saved request is found
    # If the function returns a Response object (from FastAPI or requests package), it will be used as the response for the request
    # If the function returns None, the next function in the list will be called
    return [
        forward_to_my_host,
    ]

```

The `get_forwarders` method returns an array of functions.
Each function can return a number of options:

- A `Response` object from the `fastapi` package
- A `Response` object from the `requests` package
- A `dict` object (see below for details)
- `None`

If a forwarding function returns a `Response` object then that response is used as the response for the request and is added to the recording.

If a forwarding function returns a `dict` object, it should contain a `response` property and a `persist` property.
The `response` can be from either `fastapi` or `requests`. The `persist` value is a boolean indicating whether the request/response should be persisted.
This can be useful if you are forwarding to an API that uses the [async pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/async-request-reply) as you can skip recording the intermediate responses while polling for completion and only save the final response with the completed value.

If a forwarding function returns `None` then the next forwarding function is called.
This can be useful if you need to be able to forward to multiple back-end APIs you can include logic in each forwarding function to determine whether it should take actions.

```python
async def forward_to_my_host(request: Request) -> Response | None:
	if not request.url.path.startswith("/my-api/"):
		# assume not a request this forwarder can handle
		# return None to allow another forwarder to try
		return None
	# rest of the implementation here...
```

The default forwarder can be found in `src/aoai_simulated_api/record_replay/_request_forwarder_config.py`.

### Running with a customer forwarder

To run with a custom forwarder set the `FORWARDER_CONFIG_PATH` environment variable:

```bash
SIMULATOR_MODE=record FORWARDER_CONFIG_PATH=/path/to/forwarder_config.py uvicorn main:app --reload --port 8000
```

Or via Docker:

```bash
docker run -p 8000:8000 -e SIMULATOR_MODE=record -e FORWARDER_CONFIG_PATH=/aoai/forwarder_config.py -v /path/to/forwarder_config.py:/aoai aoai-simulated-api
```

## Large recordings

By default, the simulator saves the recording file after each new recorded request in `record` mode.
If you need to create a large recording, you may want to turn off the autosave feature to improve performance.

With autosave off, you can save the recording manually by sending a `POST` request to `/++/save-recordings` to save the recordings files once you have made all the requests you want to capture. You can do this using ` curl localhost:8000/++/save-recordings -X POST`. 

## Current Status/Notes

### Replay Exploration

The initial implementation of the simulator used VCR.py and was very quick to code up and had good perf for small recordings.

The custom implementation loads the YAML once and then does a lookup using a dictionary based on a hash of the request data (method, URL, and body).
This still uses the same serialisation format as VCR.py (YAML) for convenience.

The custom implementation with `yaml.CLoader` is the same as the custom implementation but uses the `yaml.CLoader` to load the YAML file, which improves the load perf!
This is the current implementation used in the project.

Timings for replay exploration are below. Results are in the format `initial time (repeat time)` 

| # Interactions | YAML Size | Time/request with VCR | Time/request with custom | Time/request with custom + yaml.CLoader |
| -------------- | --------- | --------------------- | ------------------------ | --------------------------------------- |
| 1000           | 1.4 MB    | 0.8s (0.8s)           | 3.4s (0.6s)              | 0.8s (0.6s)                             |
| 10,000         | 14 MB     | 4s (4s)               | 25s (0.6s)               | 4s (0.6s)                               |
| 100,000        | 140 MB    | 44s (44s)             | 4m26s (0.7s)             | 44s (0.7s)                              |


