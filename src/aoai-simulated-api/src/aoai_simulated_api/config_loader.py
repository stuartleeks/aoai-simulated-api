import importlib
import json
import logging
import os

import sys

from aoai_simulated_api.limiters import get_default_limiters
from aoai_simulated_api.models import Config, OpenAIDeployment, OpenAIEmbeddingDeployment
from aoai_simulated_api.record_replay.handler import get_default_forwarders
from aoai_simulated_api.generator.manager import get_default_generators


def get_config_from_env_vars(logger: logging.Logger) -> Config:
    """
    Load configuration from environment variables
    """
    config = Config(generators=get_default_generators())
    config.recording.forwarders = get_default_forwarders()
    config.openai_deployments = _load_openai_deployments(logger)
    config.openai_embedding_deployments = \
        _load_openai_embedding_deployments(logger)

    if not config.openai_deployments:
        logger.info("OpenAI deployments not set - using default OpenAI deployments")
        config.openai_deployments = _default_openai_deployments()

    # If there are no OpenAI embedding deployments, use the default model
    if not config.openai_embedding_deployments:
        logger.info("OpenAI embedding deployments not set - "
                    "using default OpenAI embedding deployments")
        config.openai_embedding_deployments = \
            _default_openai_embedding_deployments()

    initialize_config(config)
    return config


def initialize_config(config: Config):
    config.limiters = get_default_limiters(config)

    # load extension and invoke to update config (customise forwarders, generators, etc.)
    load_extension(config)


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

def _load_openai_embedding_deployments(logger: logging.Logger) -> dict[str, OpenAIDeployment]:
    """
    Load OpenAI deployment configurations from json file at location
    specified by OPENAI_EMBEDDING_DEPLOYMENT_CONFIG_PATH environment variable.

    Args:
        logger: Logger instance to log messages

    Returns:
        dict: OpenAI deployment configurations
    """
    openai_embedding_deployment_config_path = \
        os.getenv("OPENAI_EMBEDDING_DEPLOYMENT_CONFIG_PATH")

    if not openai_embedding_deployment_config_path:
        logger.info("No OpenAI embedding deployment configuration found")
        return None

    if not os.path.isabs(openai_embedding_deployment_config_path):
        logger.error("OpenAI embedding deployment "
                     "configuration file not found: %s",
                     openai_deployment_config_path)
        return None
        
    deployments = {}
    for model_name, size in config_json.items():
        deployments[model_name] = OpenAIEmbeddingDeployment(
            name=deployment_name,
            size=size
        )
    return deployments
    

def _default_openai_embedding_deployments() \
        -> dict[str, OpenAIEmbeddingDeployment]:
    """
    Returns the default set of OpenAI embedding deployment configurations

    Returns:
        dict: OpenAI embedding deployment configurations
    """

    return {
        "text-embedding-ada-002": OpenAIEmbeddingDeployment(
            name="text-embedding-ada-002", size=1536
        ),
    }

def _default_openai_deployments() -> dict[str, OpenAIDeployment]:
    # Default set of OpenAI deployment configurations for when none are provided
    return {
        "embedding": OpenAIDeployment(name="embedding", model="text-embedding-ada-002", tokens_per_minute=10000),
        "gpt-35-turbo-1k-token": OpenAIDeployment(
            name="gpt-35-turbo-1k-token", model="gpt-3.5-turbo", tokens_per_minute=1000
        ),
        "gpt-35-turbo-2k-token": OpenAIDeployment(
            name="gpt-35-turbo-2k-token", model="gpt-3.5-turbo", tokens_per_minute=2000
        ),
        "gpt-35-turbo-5k-token": OpenAIDeployment(
            name="gpt-35-turbo-5k-token", model="gpt-3.5-turbo", tokens_per_minute=5000
        ),
        "gpt-35-turbo-10k-token": OpenAIDeployment(
            name="gpt-35-turbo-10k-token", model="gpt-3.5-turbo", tokens_per_minute=10000
        ),
        "gpt-35-turbo-20k-token": OpenAIDeployment(
            name="gpt-35-turbo-20k-token", model="gpt-3.5-turbo", tokens_per_minute=20000
        ),
        "gpt-35-turbo-50k-token": OpenAIDeployment(
            name="gpt-35-turbo-50k-token", model="gpt-3.5-turbo", tokens_per_minute=50000
        ),
        "gpt-35-turbo-100k-token": OpenAIDeployment(
            name="gpt-35-turbo-100k-token", model="gpt-3.5-turbo", tokens_per_minute=100000
        ),
        "gpt-35-turbo-100m-token": OpenAIDeployment(
            name="gpt-35-turbo-100m-token", model="gpt-3.5-turbo", tokens_per_minute=100000000
        ),
    }


def load_extension(config: Config):

    extension_path = config.extension_path
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
    initialize_config(new_config)
    _config = new_config
