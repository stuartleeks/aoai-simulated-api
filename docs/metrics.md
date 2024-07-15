# API Metrics

To help you understand how the API Simulator is performing, we provide a number of metrics that you can use to monitor the simulator.

- [API Metrics](#api-metrics)
	- [aoai-simulator.latency.base](#aoai-simulatorlatencybase)
	- [aoai-simulator.latency.full](#aoai-simulatorlatencyfull)
	- [aoai-simulator.tokens.used](#aoai-simulatortokensused)
	- [aoai-simulator.tokens.requested](#aoai-simulatortokensrequested)
	- [aoai-simulator.limits](#aoai-simulatorlimits)


## aoai-simulator.latency.base

Units: `seconds`


The `aoai-simulator.latency.base` metric measures the base latency of the simulator. This is the time taken to process a request _excluding_ any added latency.

Dimensions:
- `deployment`: The name of the deployment the metric relates to.
- `status_code`: The HTTP status code of the response.

## aoai-simulator.latency.full

Units: `seconds`

The `aoai-simulator.latency.full` metric measures the full latency of the simulator. This is the time taken to process a request _including_ any added latency.

Dimensions:
- `deployment`: The name of the deployment the metric relates to.
- `status_code`: The HTTP status code of the response.


## aoai-simulator.tokens.used

Units: `tokens`

The `aoai-simulator.tokens.used` metric measures the number of tokens used by the simulator in producing successful responses.

Dimensions:
- `deployment`: The name of the deployment the metric relates to.
- `token_type`: The type of token, e.g. `prompt` or `completion`.

## aoai-simulator.tokens.requested

Units: `tokens`

The `aoai-simulator.tokens.requested` metric measures the number of tokens requested. This is the total requested load on the simulator, including requests that were rate-limited.

Dimensions:
- `deployment`: The name of the deployment the metric relates to.
- `token_type`: The type of token, e.g. `prompt` or `completion`.

## aoai-simulator.limits

Units: `requests`

The `aoai-simulator.limits` metric measures the number of requests that were rate-limited by the simulator.

Dimensions:
- `deployment`: The name of the deployment the metric relates to.
- `limit_type`: The type of limit that was hit, e.g. `requests` or `tokens`.