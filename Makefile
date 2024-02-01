SHELL=/bin/bash

help: ## show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%s\033[0m|%s\n", $$1, $$2}' \
	| column -t -s '|'


install-requirements:
	pip install -r src/aoai-simulated-api/requirements.txt
	pip install -r src/test-client/requirements.txt

run-simulated-api:
	set -a && \
	source .env && \
	set +a && \
	cd src/aoai-simulated-api && \
	uvicorn main:app --reload --port 8000


run-test-client:
	set -a && \
	source .env && \
	set +a && \
	cd src/test-client && \
	python app.py

run-test-client-simulator:
	set -a && \
	source .env && \
	set +a && \
	cd src/test-client && \
	AZURE_OPENAI_ENDPOINT=http://localhost:8000 python app.py