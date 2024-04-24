# aoai-simulated-api

This repo is an exploration into creating a simulated API implementation for Azure OpenAI (AOAI). This is a work in progress!

- [aoai-simulated-api](#aoai-simulated-api)
  - [Rationale](#rationale)
  - [Overview](#overview)
  - [Getting Started](#getting-started)
  - [Running in Docker](#running-in-docker)
  - [Deploying to Azure Container Apps](#deploying-to-azure-container-apps)
  - [Extending the simulator](#extending-the-simulator)
    - [Creating a custom forwarder extension](#creating-a-custom-forwarder-extension)
    - [Creating a custom generator extension](#creating-a-custom-generator-extension)
    - [Running with an extension](#running-with-an-extension)
  - [Large recordings](#large-recordings)
  - [Latency](#latency)
  - [Rate-limiting](#rate-limiting)
    - [OpenAI Rate-Limiting](#openai-rate-limiting)
    - [Document Intelligence Rate-Limiting](#document-intelligence-rate-limiting)
  - [Config Endpoint](#config-endpoint)
  - [Current Status/Notes](#current-statusnotes)
    - [Replay Exploration](#replay-exploration)
    - [Using the simulator with restricted network access](#using-the-simulator-with-restricted-network-access)
      - [Unrestricted Network Access](#unrestricted-network-access)
      - [Semi-Restricted Network Access](#semi-restricted-network-access)
      - [Restricted Network Access](#restricted-network-access)


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

| Variable                        | Description                                                                                                                                                                                             |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `SIMULATOR_MODE`                | The mode the simulator should run in. Current options are `record`, `replay`, and `generate`.                                                                                                           |
| `SIMULATOR_API_KEY`             | The API key used by the simulator to authenticate requests. If not specified a key is auto-generated (see the logs). It is recommended to set a deterministic key value in `.env`                       |
| `RECORDING_DIR`                 | The directory to store the recorded requests and responses (defaults to `.recording`).                                                                                                                  |
| `RECORDING_AUTOSAVE`            | If set to `True` (default), the simulator will save the recording after each request.                                                                                                                   |
| `EXTENSION_PATH`                | The path to a Python file that contains the extension configuration. This can be a single python file or a package folder - see `src/examples`                                                          |
| `AZURE_OPENAI_ENDPOINT`         | The endpoint for the Azure OpenAI service, e.g. `https://mysvc.openai.azure.com/`                                                                                                                       |
| `AZURE_OPENAI_KEY`              | The API key for the Azure OpenAI service.                                                                                                                                                               |
| `DOC_INTELLIGENCE_RPS`          | The rate limit for the Document Intelligence service. Defaults to 15 RPS. See [Doc Intelligence Rate-Limiting](#document-intelligence-rate-limiting). Set to a negative value to disable rate-limiting. |
| `OPENAI_DEPLOYMENT_CONFIG_PATH` | The path to a JSON file that contains the deployment configuration. See [OpenAI Rate-Limiting](#openai-rate-limiting)                                                                                   |
| `AZURE_OPENAI_DEPLOYMENT`       | Used by the test app to set the name of the deployed model in your Azure OpenAI service. Use a gpt-35-turbo-instruct deployment.                                                                        |
| `LOG_LEVEL`                     | The log level for the simulator. Defaults to `INFO`.                                                                                                                                                    |
| `LATENCY_OPENAI_*`              | The latency to add to the OpenAI service when using generated output. See [Latency](#latency) for more details.                                                                                         |

The examples below show passing environment variables to the API directly on the command line, but you can also set them via a `.env` file in the root directory for convenience (see the `sample.env` for a starting point).
The `.http` files for testing the endpoints also use the `.env` file to set the environment variables for calling the API.

> Note: when running the simulator it will auto-generate an API. This needs to be passed to the API when making requests. To avoid the API Key changing each time the simulator is run, set the `SIMULATOR_API_KEY` environment variable to a fixed value.

To run the simulated API, run `make run-simulated-api` from the repo root directory using the environment variables above to configure.

For example, to use the API in record/replay mode:

```bash
# Run the API in record mode
SIMULATOR_MODE=record AZURE_OPENAI_ENDPOINT=https://mysvc.openai.azure.com/ AZURE_OPENAI_KEY=your-api-key make run-simulated-api

# Run the API in replay mode
SIMULATOR_MODE=replay make run-simulated-api
```

To run the API in generator mode, you can set the `SIMULATOR_MODE` environment variable to `generate` and run the API as above.

```bash
# Run the API in generator mode
SIMULATOR_MODE=generate make run-simulated-api
```

## Running in Docker

If you want to run the API simulator as a Docker container, there is a `Dockerfile` that can be used to build the image.

To build the image, run `docker build -t aoai-simulated-api .` from the `src/aoai-simulated-api` folder.

Once the image is built, you can run is using `docker run -p 8000:8000 -e SIMULATOR_MODE=record -e AZURE_OPENAI_ENDPOINT=https://mysvc.openai.azure.com/ -e AZURE_OPENAI_KEY=your-api-key aoai-simulated-api`.

Note that you can set any of the environment variable listed in the [Getting Started](#getting-started) section when running the container.
For example, if you have the recordings on your host (in `/some/path`) , you can mount that directory into the container using the `-v` flag: `docker run -p 8000:8000 -e SIMULATOR_MODE=replay -e RECORDING_DIR=/recording -v /some/path:/recording aoai-simulated-api`.

## Deploying to Azure Container Apps

The simulated API can be deployed to Azure Container Apps (ACA) to provide a publicly accessible endpoint for testing with the rest of your system:

Before deploying, set up a `.env` file. See the `sample.env` file for a starting point and add any configuration variables.
Once you have your `.env` file, run `make deploy-aca`. This will deploy a container registry, build and push the simulator image to it, and deploy an Azure Container App running the simulator with the settings from `.env`.

The ACA deployment also creates an Azure Storage account with a file share. This file share is mounted into the simulator container as `/mnt/simulator`.
If no value is specified for `RECORDING_DIR`, the simulator will use `/mnt/simulator/recording` as the recording directory.

The file share can also be used for setting the OpenAI deployment configuration or for any forwarder/generator config.

## Extending the simulator

The simulator allows extending some aspects of the behavior without modifying the original source code.

The `EXTENSION_PATH` environment variable can be set to the path to an extension.
This can be a single python file or a package folder.
The extension should contain an `initialize` method that receives the simulator configuration and can modify it.

### Creating a custom forwarder extension

When running in `record` mode, the simulator forwards requests on to a backend API and records the request/response information for later replay.

The default implementation uses the `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_KEY` environment variables to forward requests on to Azure OpenAI.

To forward requests on to a different backend API, you can create a custom forwarder extension.

An extension needs to have an `initialize` method as shown below:

```python
from typing import Callable
from fastapi import Request
import requests

from aoai_simulated_api.models import Config

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

def initialize(config: Config):
    # initialize is the entry point invoked by the simulator
    # here we append the custom forwarder to the list of forwarders
    config.recording.forwarders.append(forward_to_my_host)
```

The `initialize` method receives the simulator config and can manipulate it to change the simulator behavior.

The `config.recording.forwarders` property is a list of functions that are called in order to forward requests on to the backend API.
Each function can by sync or async and can return a number of options:

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

### Creating a custom generator extension

If you want to add custom logic to generate responses in `generate` mode, you can create a custom generator extension.
This allows you to replace the default lorem ipsum responses with responses that are more relevant to your scenario, or are based on the input request.

An extension needs to have an `initialize` method as shown below:

```python
from aoai_simulated_api.models import Config, RequestContext
from fastapi import Response

def initialize(config: Config):
    # initialize is the entry point invoked by the simulator
    # here we append the custom generator to the list of generators
    config.generators.append(generate_echo_response)

async def generate_echo_response(context: RequestContext) -> Response | None:
    request = context.request
    if request.url.path != "/echo" or request.method != "POST":
        return None
    request_body = await request.body()
    return Response(content=f"Echo: {request_body.decode("utf-8")}", status_code=200)
```

If the generator function returns a `Response` object then that response is used as the response for the request.
If the generator function returns `None` then the next generator function is called.


### Running with an extension

To run with an extension,  set the `EXTENSION_PATH` environment variable:

```bash
SIMULATOR_MODE=record EXTENSION_PATH=/path/to/extension.py make run-simulated-api
```

Or via Docker:

```bash
docker run -p 8000:8000 -e SIMULATOR_MODE=record -e EXTENSION_PATH=/mnt/extension.py -v /path/to/extension.py:/mnt/extension.py
```

## Large recordings

By default, the simulator saves the recording file after each new recorded request in `record` mode.
If you need to create a large recording, you may want to turn off the autosave feature to improve performance.

With autosave off, you can save the recording manually by sending a `POST` request to `/++/save-recordings` to save the recordings files once you have made all the requests you want to capture. You can do this using ` curl localhost:8000/++/save-recordings -X POST`. 

## Latency

When running in `record` mode, the simulator captures the duration of the forwarded response.
This is stored in the recording file and used to add latency to requests in `replay` mode.

When running in `generate` mode, the simulator can add latency to the response based on the `LATENCY_OPENAI_*` environment variables.

| Variable Prefix                   | Description                                                                                                                                                                        |
| --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `LATENCY_OPENAI_EMBEDDINGS`       | Speficy the latency to add to embeddings requests in milliseconds using `LATENCY_OPENAI_EMBEDDINGS_MEAN` and `LATENCY_OPENAI_EMBEDDINGS_STD_DEV`                                   |
| `LATENCY_OPENAI_COMPLETIONS`      | Specify the latency to add to completions _per completion token_ in milliseconds using `LATENCY_OPEN_AI_COMPLETIONS_MEAN` and `LATENCY_OPEN_AI_COMPLETIONS_STD_DEV`                |
| `LATENCY_OPENAI_CHAT_COMPLETIONS` | Specify the latency to add to chat completions _per completion token_ in milliseconds using `LATENCY_OPEN_AI_CHAT_COMPLETIONS_MEAN` and `LATENCY_OPEN_AI_CHAT_COMPLETIONS_STD_DEV` |


The default values are:

| Prefix                            | Mean | Std Dev |
| --------------------------------- | ---- | ------- |
| `LATENCY_OPENAI_EMBEDDINGS`       | 100  | 30      |
| `LATENCY_OPENAI_COMPLETIONS`      | 15   | 2       |
| `LATENCY_OPENAI_CHAT_COMPLETIONS` | 19   | 6       |


## Rate-limiting

The rate-limiting implementation is configured differently depending on the type of request being handled.

Rate-limiting is applied regardless of the mode the simulator is running in.

### OpenAI Rate-Limiting

Rate-limiting for OpenAI endpoints is still being implemented/tested. The current implementation is a combination of token- and request-based rate-limiting.

To control the rate-limiting, set the `OPENAI_DEPLOYMENT_CONFIG_PATH` environment variable to the path to a JSON config file that defines the deployments and associated models and token limits. An example config file is shown below.

```json
{
	"deployment1" : {
		"model": "gpt-3.5-turbo",
		"tokensPerMinute" : 60000
	},
	"gpt-35-turbo-2k-token" : {
		"model": "gpt-3.5-turbo",
		"tokensPerMinute" : 2000
	},
	"gpt-35-turbo-1k-token" : {
		"model": "gpt-3.5-turbo",
		"tokensPerMinute" : 1000
	}
}
```

### Document Intelligence Rate-Limiting

Rate-limiting for Document Intelligence endpoints is a standard requests per second (RPS) limit. The default limit for the simulator is 15 RPS based on the default for an S0 tier service (see https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/service-limits?view=doc-intel-4.0.0).

This rate-limit only applies to the request submission endpoint and not to the results endpoint.

To control the rate-limiting, set the `DOC_INTELLIGENCE_RPS` environment variable to the desired RPS limit.

## Config Endpoint

The simulator exposes a `/++/config` endpoint that returns the current configuration of the simulator and allow the configuration to be updated dynamically.

A `GET` request to this endpoint will return a JSON object with the current configuration:

```json
{"simulator_mode":"generate","doc_intelligence_rps":15,"latency":{"open_ai_embeddings":{"mean":100.0,"std_dev":30.0},"open_ai_completions":{"mean":15.0,"std_dev":2.0},"open_ai_chat_completions":{"mean":19.0,"std_dev":6.0}},"openai_deployments":{"deployment1":{"tokens_per_minute":60000,"model":"gpt-3.5-turbo"},"gpt-35-turbo-1k-token":{"tokens_per_minute":1000,"model":"gpt-3.5-turbo"}}}
```

A `PATCH` request can be used to update the configuration
The body of the request should be a JSON object with the configuration values to update.

For example, the following request will update the mean latency for OpenAI embeddings to 1 second (1000ms):

```json
{"latency": {"open_ai_embeddings": {"mean": 1000}}}
```

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

### Using the simulator with restricted network access

During initialization, TikToken attempts to download an OpenAI encoding file from a public blob storage account managed by OpenAI. When running the simulator in an environment with restricted network access, this can cause the simulator to fail to start.  
  
The simulator supports three networking scenarios with different levels of access to the public internet:  
  
- Unrestricted network access  
- Semi-restricted network access  
- Restricted network access  

Different build arguments can be used to build the simulator for each of these scenarios.
#### Unrestricted Network Access  
  
In this mode, the simulator operates normally, with TikToken downloading the OpenAI encoding file from OpenAI's public blob storage account. This scenario assumes that the Docker container can access the public internet during runtime.
This is the default build mode.
  
#### Semi-Restricted Network Access  
  
The semi-restricted network access scenario applies when the build machine has access to the public internet but the runtime environment does not. In this scenario,
 the simulator can be built using the Docker build argument `network_type=semi-restricted`. This will download the TikToken encoding file during the Docker image build process and cache it within the Docker image. The build process will also set the required `TIKTOKEN_CACHE_DIR` environment variable to point to the cached TikToken encoding file. 
  
#### Restricted Network Access  
The restricted network access scenario applies when both the build machine and the runtime environment do not have access to the public internet. In this scenario, the simulator can be built using a pre-downloaded TikToken encoding file that must be included in a specific location. 

This can be done by running the [setup_tiktoken.py](./scripts/setup_tiktoken.py) script. 
Alternatively, you can download the [encoding file](https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken) from the public blob storage account and place it in the `src/aoai-simulated-api/tiktoken_cache` directory. Then rename the file to `9b5ad71b2ce5302211f9c61530b329a4922fc6a4`.

To build the simulator in this mode, set the Docker build argument `network_type=restricted`. The simulator and the build process will then use the cached TikToken encoding file instead of retrieving it through the public internet. The build process will also set the required `TIKTOKEN_CACHE_DIR` environment variable to point to the cached TikToken encoding file. 

