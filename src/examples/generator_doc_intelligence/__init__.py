from aoai_simulated_api.models import Config

from .doc_intell import doc_intelligence_analyze, doc_intelligence_analyze_result


def initialize(config: Config):
    """initialize is the entry point invoked by the simulator"""
    config.generators.append(doc_intelligence_analyze)
    config.generators.append(doc_intelligence_analyze_result)
