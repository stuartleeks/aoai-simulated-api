#!/bin/bash
set -e

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

if [[ -f "$script_dir/../.env" ]]; then
	echo "Loading .env"
	source "$script_dir/../.env"
fi


if [[ ! -f "$script_dir/../infra/output.json" ]]; then
  echo "output.json not found - have you deployed the base infra?"
  exit 1
fi

acr_login_server=$(cat $script_dir/../infra/output.json  | jq -r .containerRegistryLoginServer)
if [[ -z "$acr_login_server" ]]; then
  echo "Container registry login server not found in output.json"
  exit 1
fi
acr_name=$(cat $script_dir/../infra/output.json  | jq -r .containerRegistryName)
if [[ -z "$acr_name" ]]; then
  echo "Container registry name not found in output.json"
  exit 1
fi

echo "=="
echo "== Building and pushing aoai-simulated-api image to $acr_login_server"
echo "=="

src_path=$(realpath "$script_dir/../src/aoai-simulated-api")

docker build -t ${acr_login_server}/aoai-simulated-api:latest "$src_path" -f "$src_path/Dockerfile"

az acr login --name $acr_name
docker push ${acr_login_server}/aoai-simulated-api:latest

echo -e "\n"
