# Changelog

## vNext

- Extensibility updates
  - Focussing core simulator on OpenAI (moved doc intelligence generator to example extension)
  - API authorization is now part of forwarders/generators. If you have custom forwarders/generators they need to be updated to handle this (see examples for implementation details)


## v0.3 2024-05-03

- Improve error info when no matching handler is found
- Fix tokens-per-minute to requests-per-minute conversion bug

## v0.2 - 2024-04-24

- Add option to configure latency for generated responses for OpenAI endpoints
- Add `/++/config` endpoint to get and set configuration values

## v0.1 - 2024-04-22

Initial tagged version