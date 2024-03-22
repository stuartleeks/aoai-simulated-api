import importlib.util
import inspect
import os
import sys
from fastapi import Request
from ._generator_context import GeneratorCallContext, GeneratorSetupContext
from aoai_simulated_api.pipeline import RequestContext


def _load_generators(generator_config_path: str, setup_context: GeneratorSetupContext):
    # generator_config_path is the path to a folder with a __init__.py
    # use the last folder name as the module name as that is intuitive when the __init__.py
    # references other files in the same folder
    config_is_dir = os.path.isdir(generator_config_path)
    if config_is_dir:
        module_name = os.path.basename(generator_config_path)
        path_to_load = os.path.join(generator_config_path, "__init__.py")
    else:
        module_name = "__generator_config"
        path_to_load = generator_config_path

    module_spec = importlib.util.spec_from_file_location(module_name, path_to_load)
    module = importlib.util.module_from_spec(module_spec)
    sys.modules[module_spec.name] = module
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
