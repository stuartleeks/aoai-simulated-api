import importlib
import json
import logging
import os

import sys

from aoai_simulated_api.models import Config, LatencyConfig, NormalLatencyAmount, OpenAIDeployment, RecordingConfig
from aoai_simulated_api.record_replay.handler import get_default_forwarders
from aoai_simulated_api.generator.manager import get_default_generators
import nanoid


def get_config_from_env_vars(logger: logging.Logger) -> Config:
    """
    Load configuration from environment variables
    """
    simulator_mode = os.getenv("SIMULATOR_MODE") or "replay"
    recording_dir = os.getenv("RECORDING_DIR") or ".recording"
    recording_dir = os.path.abspath(recording_dir)
    recording_autosave = os.getenv("RECORDING_AUTOSAVE", "true").lower() == "true"

    forwarding_aoai_api_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    forwarding_aoai_api_key = os.getenv("AZURE_OPENAI_KEY")

    simulator_api_key = os.getenv("SIMULATOR_API_KEY")
    if not simulator_api_key:
        simulator_api_key = nanoid.generate(size=30)

    extension_path = os.getenv("EXTENSION_PATH")

    allowed_simulator_modes = ["replay", "record", "generate"]
    if simulator_mode not in allowed_simulator_modes:
        logger.error("SIMULATOR_MODE must be one of %s", allowed_simulator_modes)
        raise ValueError(f"Invalid SIMULATOR_MODE: {simulator_mode}")

    config = Config(
        simulator_mode=simulator_mode,
        simulator_api_key=simulator_api_key,
        recording=RecordingConfig(
            dir=recording_dir,
            autosave=recording_autosave,
            aoai_api_endpoint=forwarding_aoai_api_endpoint,
            aoai_api_key=forwarding_aoai_api_key,
            forwarders=get_default_forwarders(),
        ),
        generators=get_default_generators(),
        openai_deployments=_load_openai_deployments(logger),
        doc_intelligence_rps=load_doc_intelligence_limit(),
        latency=load_latency_config(),
    )

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


def load_doc_intelligence_limit() -> int:
    # Default is 15 RPS based on:
    # https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/service-limits?view=doc-intel-4.0.0
    return int(os.getenv("DOC_INTELLIGENCE_RPS", "15"))


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


def load_latency_normal(base_name: str, default_mean: float, default_std_dev) -> NormalLatencyAmount:
    return NormalLatencyAmount(
        mean=os.getenv(f"{base_name}_MEAN", default_mean), std_dev=os.getenv(f"{base_name}_STD_DEV", default_std_dev)
    )


def load_latency_config() -> LatencyConfig:
    return LatencyConfig(
        open_ai_completions=load_latency_normal("LATENCY_OPENAI_COMPLETIONS", 15, 2),
        open_ai_chat_completions=load_latency_normal("LATENCY_OPENAI_CHAT_COMPLETIONS", 19, 6),
        open_ai_embeddings=load_latency_normal("LATENCY_OPENAI_EMBEDDINGS", 100, 30),
    )
