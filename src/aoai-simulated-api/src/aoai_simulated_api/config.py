import json
import logging
import os

from dataclasses import dataclass

import nanoid


@dataclass
class RecordingConfig:
    dir: str
    format: str
    autosave: bool
    forwarder_config_path: str | None
    aoai_api_key: str | None = None
    aoai_api_endpoint: str | None = None


@dataclass
class Config:
    """
    Configuration for the simulator
    """

    simulator_mode: str
    simulator_api_key: str
    recording: RecordingConfig
    generator_config_path: str | None
    openai_deployments: dict[str, "OpenAIDeployment"] | None


def get_config_from_env_vars(logger: logging.Logger) -> Config:
    """
    Load configuration from environment variables
    """
    simulator_mode = os.getenv("SIMULATOR_MODE") or "replay"
    recording_dir = os.getenv("RECORDING_DIR") or ".recording"
    recording_dir = os.path.abspath(recording_dir)
    recording_format = os.getenv("RECORDING_FORMAT") or "yaml"
    recording_autosave = os.getenv("RECORDING_AUTOSAVE", "true").lower() == "true"

    forwarding_aoai_api_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    forwarding_aoai_api_key = os.getenv("AZURE_OPENAI_KEY")

    simulator_api_key = os.getenv("SIMULATOR_API_KEY")
    if not simulator_api_key:
        simulator_api_key = nanoid.generate(size=30)

    generator_config_path = os.getenv("GENERATOR_CONFIG_PATH")
    forwarder_config_path = os.getenv("FORWARDER_CONFIG_PATH")

    use_tiktoken_cache = os.getenv("USE_TIKTOKEN_CACHE", "false").lower() == "true"

    allowed_simulator_modes = ["replay", "record", "generate"]
    if simulator_mode not in allowed_simulator_modes:
        logger.error("SIMULATOR_MODE must be one of %s", allowed_simulator_modes)
        raise ValueError(f"Invalid SIMULATOR_MODE: {simulator_mode}")

    allowed_recording_formats = ["yaml", "json"]
    if recording_format not in allowed_recording_formats:
        logger.error("RECORDING_FORMAT must be one of %s", allowed_recording_formats)
        raise ValueError(f"Invalid RECORDING_FORMAT: {recording_format}")

    if use_tiktoken_cache:
        setup_tiktoken_cache()

    return Config(
        simulator_mode=simulator_mode,
        simulator_api_key=simulator_api_key,
        recording=RecordingConfig(
            dir=recording_dir,
            format=recording_format,
            autosave=recording_autosave,
            forwarder_config_path=forwarder_config_path,
            aoai_api_endpoint=forwarding_aoai_api_endpoint,
            aoai_api_key=forwarding_aoai_api_key,
        ),
        generator_config_path=generator_config_path,
        openai_deployments=_load_openai_deployments(logger),
    )


@dataclass
class OpenAIDeployment:
    name: str
    model: str
    tokens_per_minute: int


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
