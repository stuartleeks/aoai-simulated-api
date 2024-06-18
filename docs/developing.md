# Developing the API Simulator

This file contains some notes about developing the API simulator.

The simplest way to work with the simulator code is with [Dev Containers](https://code.visualstudio.com/docs/devcontainers/containers) in VS Code.
The repo contains a Dev Container configuration that sets up a container with all the dependencies needed to develop the simulator.

## Repo Contents

- `infra` contains the bicep files to deploy the simulator to Azure Container Apps
- `src` contains the simulator code and tests
- `scripts` contains scripts to help with development/deployment
- `test-aoai.http` contains a collection of HTTP requests that can be run in VS Code using the REST Client extension

Under the `src` folder ther are the following subfolders:
- `aoai_simulated_api` - the simulator code
- `examples` - example code showing how to extend the simulator
- `loadtest` - locust-based load tests for validating the simulator performance
- `test-client` -  a simple client that can be used to test the simulator interactively
- `test-client-web` -  a simple web client that can be used to demo the chat completions
- `tests` - integration tests for validating the simulator

## Running the linter/tests

There is a `Makefile` in the root of the repo that contains some useful commands.

To run the linter run `make lint`.

To run the tests run `make test`.

## Pre-release checklist

- Ensure that the tests run
- Compare the linter output to the last release - this helps to avoid accumulating a build-up of linting issues
- Deploy the simulator to Container Apps
- Run load tests against the deployed simulator (see [Load tests](#load-tests))

### Load tests

The following load tests should be run against the simulator before a release:

#### Load test: No latency, no limits

To run this test, run `./scripts/run-load-test-no-latency-no-limits.sh`.

The test sends requests to the simulator as fast as possible with no latency and no rate limiting.
This test is useful for validating the base latency and understanding the maximum throughput of the simulator.


#### Load test: 1s latency, no limits

To run this test, run `./scripts/run-load-test-1s-latency-no-limits.sh`.

The test sends requests to the simulator as fast as possible with 1s latency and no rate limiting.
This test is useful for validating the simulated latency behavior.


