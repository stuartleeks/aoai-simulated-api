from aoai_simulated_api.models import Config

from .document_intelligence_forwarder import forward_to_azure_document_intelligence


def initialize(config: Config):
    """initialize is the entry point invoked by the simulator"""
    config.recording.forwarders.append(forward_to_azure_document_intelligence)
