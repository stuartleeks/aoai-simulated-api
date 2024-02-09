import importlib.util
import inspect
from fastapi import Request


def _load_generators(generator_config_path: str):
    module_spec = importlib.util.spec_from_file_location("__module", generator_config_path)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module.get_generators()


class GeneratorManager:
    def __init__(self, generator_config_path: str = "generator_config.py"):
        # self._generators = get_generators()
        self._generators = _load_generators(generator_config_path)
        print("***", self._generators, "***")

    async def generate(self, request: Request):
        for generator in self._generators:
            response = generator(request)
            if response is not None and inspect.isawaitable(response):
                response = await response
            if response is not None:
                return response
        raise Exception("No generator found for request")
