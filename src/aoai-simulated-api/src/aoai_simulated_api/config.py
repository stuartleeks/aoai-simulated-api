import json
import logging
import os

from dataclasses import dataclass


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

    # TODO: move into config.py
    # TODO: restructure, e.g. group recording settings together
    # TODO: combine OpenAI deployment configuration
    simulator_mode: str
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

    aoai_api_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    aoai_api_key = os.getenv("AZURE_OPENAI_KEY")

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
        recording=RecordingConfig(
            dir=recording_dir,
            format=recording_format,
            autosave=recording_autosave,
            forwarder_config_path=forwarder_config_path,
            aoai_api_endpoint=aoai_api_endpoint,
            aoai_api_key=aoai_api_key,
        ),
        generator_config_path=generator_config_path,
        openai_deployments=_load_openai_deployments(),
    )


@dataclass
class OpenAIDeployment:
    name: str
    model: str
    tokens_per_minute: int


def _load_openai_deployments() -> dict[str, OpenAIDeployment]:
    openai_deployment_config_path = os.getenv("OPENAI_DEPLOYMENT_CONFIG_PATH")
    if openai_deployment_config_path and not os.path.isabs(openai_deployment_config_path):
        openai_deployment_config_path = os.path.abspath(openai_deployment_config_path)

    if openai_deployment_config_path:
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
    return None


def load_doc_intelligence_limit() -> int:
    # Default is 20 RPM based on https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/service-limits?view=doc-intel-4.0.0
    return int(os.getenv("DOC_INTELLIGENCE_RPS", "15"))


def setup_tiktoken_cache() -> None:
    tiktoken_cache_dir = os.path.join(os.path.dirname(__file__), "tiktoken_cache")

    if not os.path.exists(
        os.path.join(
            tiktoken_cache_dir,
            "9b5ad71b2ce5302211f9c61530b329a4922fc6a4",
        )
    ):
        raise Exception(f"Could not find tiktoken encoding file in {tiktoken_cache_dir}.")

    os.environ["TIKTOKEN_CACHE_DIR"] = tiktoken_cache_dir
