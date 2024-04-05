import logging
import os

from azure.monitor.opentelemetry import configure_azure_monitor

# from opentelemetry import trace

from aoai_simulated_api.config import get_config_from_env_vars
from aoai_simulated_api.app_builder import get_simulator

log_level = os.getenv("LOG_LEVEL") or "INFO"

logger = logging.getLogger(__name__)
logging.basicConfig(level=log_level)
logging.getLogger("azure").setLevel(logging.WARNING)

# Configure OpenTelemetry to use Azure Monitor with the
# APPLICATIONINSIGHTS_CONNECTION_STRING environment variable.
configure_azure_monitor()

# tracer = trace.get_tracer(__name__)

config = get_config_from_env_vars(logger)
app = get_simulator(logger=logger, config=config)
