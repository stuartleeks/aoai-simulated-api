#!/bin/bash
set -e

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# Install the simulator code in the dev container so that types are 
# available for loaded extensions (forwarders/generators)
pip install --editable "${script_dir}/../src/aoai-simulated-api"

# install requirements for convenience
make install-requirements
