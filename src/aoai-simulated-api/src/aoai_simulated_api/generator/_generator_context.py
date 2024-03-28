from ._generator_openai import azure_openai_embedding, azure_openai_completion, azure_openai_chat_completion
from ._generator_doc_intell import doc_intelligence_analyze, doc_intelligence_analyze_result


class GeneratorSetupContext:

    def __init__(self) -> None:
        self.built_in_generators = {
            "azure_openai_embedding": azure_openai_embedding,
            "azure_openai_completion": azure_openai_completion,
            "azure_openai_chat_completion": azure_openai_chat_completion,
            "doc_intelligence_analyze": doc_intelligence_analyze,
            "doc_intelligence_analyze_result": doc_intelligence_analyze_result,
        }
