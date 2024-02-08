# aoai-simulated-api

This repo is an exploration into creating a simulated API implementation for Azure OpenAI (AOAI). This is a work in progress!

## Rationale

When building solutions using Azure OpenAI there are points in the development process where you may want to test your solution against a simulated API.

One example is working to integrate Open AI into your broader application. In this case you want to have representative responses to some known requests but don't need the "AI-ness" of the service (i.e. you don't need to be able to handle arbitrary user requests). A simulated API can provide these responses more cheaply and allow you an easy way to customise the responses to check different application behaviours.

Another example is load testing. In this case you are more likely to want to be able to submit a large number of requests with representative latency and rate-limiting, but don't need the actual AI responses.

## Current status

Currently, the simulated API has some initial explorations for recording requests sent to Open AI and replaying them later. The recordings is stored in YAML files which can be edited if you want to customise the responses.

Some testing needs to be done with large recording files to see how the simulated API behaves, but it is expected that a different approach will be needed for load testing usage. In this case, handlers that can generated responses on the fly will be needed.

## Getting Started

This repo is configured with a Visual Studio Code [dev container](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) that sets up a Python environment ready to work in.

After cloning the repo, install dependencies using `make install-requirements`.

When running the simulated API, there are a number of environment variables to configure:

| Variable                | Description                                                                                 |
| ----------------------- | ------------------------------------------------------------------------------------------- |
| `SIMULATOR_MODE`        | The mode the simulator should run in. Current options are `record` and `replay`.            |
| `AZURE_OPENAI_ENDPOINT` | The endpoint for the Azure OpenAI service, e.g. `https://mysvc.openai.azure.com/`           |
| `AZURE_OPENAI_KEY`      | The API key for the Azure OpenAI service.                                                   |
| `CASSETTE_DIR`          | The directory to store the recorded requests and responses (defaults to `.cassette`).       |
| `CASSETTE_FORMAT`       | Either `yaml` (default) or `json` to specify the format of the recorded requests/responses. |


To run the simulated API, run `uvicorn main:app --reload --port 8000` from the `src/aoai-simulated-api` directory.

## Running in Docker

If you want to run the API simulator as a Docker container, there is a `Dockerfile` that can be used to build the image.

To build the image, run `docker build -t aoai-simulated-api .` from the `src/aoai-simulated-api` folder.

Once the image is built, you can run is using `docker run -p 8000:8000 -e SIMULATOR_MODE=record -e AZURE_OPENAI_ENDPOINT=https://mysvc.openai.azure.com/ -e AZURE_OPENAI_KEY=your-api-key aoai-simulated-api`.

Note that you can set any of the environment variable listed in the [Getting Started](#getting-started) section when running the container.
For example, if you have the recordings on your host (in `/some/path`) , you can mount that directory into the container using the `-v` flag: `docker run -p 8000:8000 -e SIMULATOR_MODE=replay -e CASSETTE_DIR=/cassettes -v /some/path:/cassettes aoai-simulated-api`.


