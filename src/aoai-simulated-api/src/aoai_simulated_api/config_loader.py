import importlib
import json
import logging
import os

import sys

from aoai_simulated_api.models import Config, OpenAIDeployment
from aoai_simulated_api.record_replay.handler import get_default_forwarders
from aoai_simulated_api.generator.manager import get_default_generators


def get_config_from_env_vars(logger: logging.Logger) -> Config:
    """
    Load configuration from environment variables
    """
    config = Config(generators=get_default_generators())

    config.recording.forwarders = get_default_forwarders()
    config.openai_deployments = _load_openai_deployments(logger)
    extension_path = os.getenv("EXTENSION_PATH")

    # load extension and invoke to update config (customise forwarders, generators, etc.)
    load_extension(extension_path, config)
    return config


def _load_openai_deployments(logger: logging.Logger) -> dict[str, OpenAIDeployment]:
    openai_deployment_config_path = os.getenv("OPENAI_DEPLOYMENT_CONFIG_PATH")

    if not openai_deployment_config_path:
        logger.info("No OpenAI deployment configuration found")
        return None

    if not os.path.isabs(openai_deployment_config_path):
        openai_deployment_config_path = os.path.abspath(openai_deployment_config_path)

    if not os.path.exists(openai_deployment_config_path):
        logger.error("OpenAI deployment configuration file not found: %s", openai_deployment_config_path)
        return None

    with open(openai_deployment_config_path, encoding="utf-8") as f:
        config_json = json.load(f)
    deployments = {}
    for deployment_name, deployment in config_json.items():
        deployments[deployment_name] = OpenAIDeployment(
            name=deployment_name,
            model=deployment["model"],
            tokens_per_minute=deployment["tokensPerMinute"],
        )
    return deployments


def load_extension(extension_path: str, config: Config):

    if not extension_path:
        return

    # extension_path can either be a single python file or the path to a folder with a __init__.py
    # If an __init__.py, use the last folder name as the module name as that is intuitive when the __init__.py
    # references other files in the same folder
    config_is_dir = os.path.isdir(extension_path)
    if config_is_dir:
        module_name = os.path.basename(extension_path)
        path_to_load = os.path.join(extension_path, "__init__.py")
    else:
        module_name = "__extension"
        path_to_load = extension_path

    module_spec = importlib.util.spec_from_file_location(module_name, path_to_load)
    module = importlib.util.module_from_spec(module_spec)
    sys.modules[module_spec.name] = module
    module_spec.loader.exec_module(module)
    module.initialize(config)


# pylint: disable-next=invalid-name
_config = None


def get_config() -> Config:
    if not _config:
        raise ValueError("Config not set")
    return _config


def set_config(new_config: Config):
    # pylint: disable-next=global-statement
    global _config
    _config = new_config
