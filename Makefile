SHELL=/bin/bash

ifneq (,$(wildcard ./.env))
    include .env
    export
endif

makefile_dir := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

help: ## Show this help
	@grep -E '[a-zA-Z_-]+:.*?## .*$$' $(firstword $(MAKEFILE_LIST)) \
	| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-32s\033[0m %s\n", $$1, $$2}'

install-requirements: ## Install PyPI requirements for all projects
	pip install -r src/aoai-simulated-api/requirements.txt
	pip install -r src/tests/requirements.txt
	pip install -r src/test-client/requirements.txt
	pip install -r src/loadtest/requirements.txt
	pip install -r src/test-client-web/requirements.txt

erase-recording: ## Erase all *.recording files
	rm -rf "${makefile_dir}.recording"

run-simulated-api: ## Launch the AOAI Simulated API locally
	gunicorn \
		aoai_simulated_api.main:app \
		--worker-class uvicorn.workers.UvicornWorker \
		--workers 1 \
		--bind 0.0.0.0:8000 \
		--timeout 3600

run-test-client: ## Run the test client
	cd src/test-client && \
	python app.py

run-test-client-simulator-local: ## Run the test client against local AOAI Simulated API 
	cd src/test-client && \
	AZURE_OPENAI_KEY=${SIMULATOR_API_KEY} \
	AZURE_OPENAI_ENDPOINT=http://localhost:8000 \
	AZURE_FORM_RECOGNIZER_ENDPOINT=http://localhost:8000 \
	AZURE_FORM_RECOGNIZER_KEY=${SIMULATOR_API_KEY} \
	python app.py

run-test-client-simulator-aca: ## Run the test client against an Azure Container Apps deployment
	./scripts/run-test-client-aca.sh

run-test-client-web: ## Launch the test client web app locally
	cd src/test-client-web && \
	flask run --host 0.0.0.0

docker-build-simulated-api: ## Build the AOAI Simulated API as a docker image
	# TODO should set a tag!
	cd src/aoai-simulated-api && \
	docker build -t aoai-simulated-api .

docker-run-simulated-api: ## Run the AOAI Simulated API docker container
	echo "makefile_dir: ${makefile_dir}"
	echo "makefile_path: ${makefile_path}"
	docker run --rm -i -t \
		-p 8000:8000 \
		-v "${makefile_dir}.recording":/mnt/recording \
		-e RECORDING_DIR=/mnt/recording \
		-e SIMULATOR_MODE \
		-e SIMULATOR_API_KEY \
		-e AZURE_OPENAI_ENDPOINT \
		-e AZURE_OPENAI_KEY \
		-e AZURE_OPENAI_DEPLOYMENT \
		aoai-simulated-api

test: ## Run PyTest (verbose)
	pytest ./src/tests -v

test-not-slow: ## Run PyTest (verbose, skip slow tests)
	pytest ./src/tests -v -m "not slow"

test-watch: ## Start PyTest Watch
	ptw --clear ./src/tests

lint: ## Lint aoai-simulated-api source code
	pylint ./src/aoai-simulated-api/

deploy-aca: ## Run deployment script for Azure Container Apps
	./scripts/deploy-aca.sh

docker-build-load-test: ## Build the AOAI Simulated API Load Test as a docker image
	# TODO should set a tag!
	cd src/loadtest && \
	docker build -t aoai-simulated-api-load-test .
