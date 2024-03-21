import importlib.util
import inspect
from fastapi import Request
from ._generator_context import GeneratorCallContext, GeneratorSetupContext
from pipeline import RequestContext


def _load_generators(generator_config_path: str, setup_context: GeneratorSetupContext):
    module_spec = importlib.util.spec_from_file_location("__generators_module", generator_config_path)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module.get_generators(setup_context)


class GeneratorManager:
    def __init__(self, generator_config_path: str):
        self._call_context = GeneratorCallContext()
        setup_context = GeneratorSetupContext()
        self._generators = _load_generators(generator_config_path, setup_context)

    async def generate(self, context: RequestContext):
        request = context.request
        for generator in self._generators:
            response = generator(context=self._call_context, request=request)
            if response is not None and inspect.isawaitable(response):
                response = await response
            if response is not None:
                return response
        raise Exception("No generator found for request")
