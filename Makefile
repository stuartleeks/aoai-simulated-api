SHELL=/bin/bash

ifneq (,$(wildcard ./.env))
    include .env
    export
endif

makefile_dir := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

help: ## show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%s\033[0m|%s\n", $$1, $$2}' \
	| column -t -s '|'


install-requirements:
	pip install -r src/aoai-simulated-api/requirements.txt
	pip install -r src/tests/requirements.txt
	pip install -r src/test-client/requirements.txt
	pip install -r src/loadtest/requirements.txt
	pip install -r src/test-client-web/requirements.txt

erase-recording:
	rm -rf src/aoai-simulated-api/.recording

run-simulated-api:
	gunicorn \
		aoai_simulated_api.main:app \
		--worker-class uvicorn.workers.UvicornWorker \
		--workers 1 \
		--bind 0.0.0.0:8000 \
		--timeout 3600

run-test-client:
	cd src/test-client && \
	python app.py

run-test-client-simulator-local:
	cd src/test-client && \
	AZURE_OPENAI_KEY=${SIMULATOR_API_KEY} \
	AZURE_OPENAI_ENDPOINT=http://localhost:8000 \
	AZURE_FORM_RECOGNIZER_ENDPOINT=http://localhost:8000 \
	AZURE_FORM_RECOGNIZER_KEY=${SIMULATOR_API_KEY} \
	python app.py

run-test-client-simulator-aca:
	./scripts/run-test-client-aca.sh

run-test-client-web:
	cd src/test-client-web && \
	flask run --host 0.0.0.0

docker-build-simulated-api:
	# TODO should set a tag!
	cd src/aoai-simulated-api && \
	docker build -t aoai-simulated-api .

docker-run-simulated-api:
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

test:
	pytest ./src/tests -v
	
test-watch:
	ptw --clear ./src/tests

lint:
	pylint ./src/aoai-simulated-api/

deploy-aca: 
	./scripts/deploy-aca.sh

locust-completions-100k:
	LOCUST_WEB_PORT=8090 \
	locust \
		-f ./src/loadtest/test_completions_100k.py \
		-H http://localhost:8000/ \
		--users 20 \
		--spawn-rate 0.5 \
		--autostart

locust-chat-completions-100k:
	LOCUST_WEB_PORT=8090 \
	locust \
		-f ./src/loadtest/test_chat_completions_100k.py \
		-H http://localhost:8000/ \
		--users 20 \
		--spawn-rate 0.5 \
		--autostart

locust-chat-completions-100m:
	LOCUST_WEB_PORT=8090 \
	locust \
		-f ./src/loadtest/test_chat_completions_100m.py \
		-H http://localhost:8000/ \
		--users 20 \
		--spawn-rate 0.5 \
		--autostart
		
locust-chat-completions-no-limit:
	LOCUST_WEB_PORT=8090 \
	locust \
		-f ./src/loadtest/test_chat_completions_no_limit.py \
		-H http://localhost:8000/ \
		--users 20 \
		--spawn-rate 0.5 \
		--autostart



locust-doc-intell:
	LOCUST_WEB_PORT=8090 \
	locust \
		-f ./src/loadtest/test_doc_intell.py \
		-H http://localhost:8000/ \
		--users 20 \
		--spawn-rate 0.5 \
		--autostart
