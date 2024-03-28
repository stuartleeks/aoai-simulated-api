import logging
import os

from aoai_simulated_api.app_builder import get_config_from_env_vars, get_simulator

log_level = os.getenv("LOG_LEVEL") or "INFO"

logger = logging.getLogger(__name__)
logging.basicConfig(level=log_level)

config = get_config_from_env_vars(logger)
app = get_simulator(logger=logger, config=config)
