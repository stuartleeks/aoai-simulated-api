from dataclasses import dataclass
import json
import os


@dataclass
class OpenAIDeployment:
    name: str
    model: str
    tokens_per_minute: int


def load_openai_deployments() -> dict[str, OpenAIDeployment]:
    openai_deployment_config_path = os.getenv("OPENAI_DEPLOYMENT_CONFIG_PATH")
    if openai_deployment_config_path and not os.path.isabs(openai_deployment_config_path):
        openai_deployment_config_path = os.path.abspath(openai_deployment_config_path)

    if openai_deployment_config_path:
        with open(openai_deployment_config_path) as f:
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
        raise Exception("tiktoken directory does not exist!")

    os.environ["TIKTOKEN_CACHE_DIR"] = tiktoken_cache_dir
