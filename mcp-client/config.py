import os
import toml
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# --- Configuration Constants ---
# Default values, can be overridden by config file
HEARTBEAT_INTERVAL_SECONDS = 60 # Check every 60 seconds (Adjusted back to original default)
HEARTBEAT_TIMEOUT_SECONDS = 180 # Disconnect after 180 seconds of no response
HTTP_TIMEOUT_SECONDS = 10 # Timeout for HTTP health checks
RECONNECTION_INTERVAL_SECONDS = 60 # Try reconnecting every 60 seconds

def load_app_config(pyproject_file: Optional[str] = None) -> Dict[str, Any]:
    """Loads configuration from pyproject.toml."""
    if pyproject_file is None:
        current_dir = os.path.dirname(__file__)
        # Assumes config.py is in the same dir as main.py, and pyproject.toml is one level up
        pyproject_file = os.path.join(current_dir, "..", "pyproject.toml")
        # Adjust if your structure differs
        # pyproject_file = os.path.join(current_dir, "pyproject.toml")

    # Default config values
    config_data = {
        "zhipu_api_key": None,
        "zhipu_model": None,
        "heartbeat_interval": HEARTBEAT_INTERVAL_SECONDS,
        "heartbeat_timeout": HEARTBEAT_TIMEOUT_SECONDS,
        "http_timeout": HTTP_TIMEOUT_SECONDS,
        "reconnection_interval": RECONNECTION_INTERVAL_SECONDS,
    }

    try:
        logger.info(f"Loading configuration from: {pyproject_file}")
        with open(pyproject_file, "r", encoding="utf-8") as f:
            config = toml.load(f)

        # Load Zhipu settings
        zhipu_config = config.get("tool", {}).get("zhipu", {})
        config_data["zhipu_api_key"] = zhipu_config.get("openai_api_key", config_data["zhipu_api_key"])
        config_data["zhipu_model"] = zhipu_config.get("model", config_data["zhipu_model"])

        # Load timing settings if present in config
        timing_config = config.get("tool", {}).get("timing", {})
        config_data["heartbeat_interval"] = timing_config.get("heartbeat_interval_seconds", config_data["heartbeat_interval"])
        config_data["heartbeat_timeout"] = timing_config.get("heartbeat_timeout_seconds", config_data["heartbeat_timeout"])
        config_data["http_timeout"] = timing_config.get("http_timeout_seconds", config_data["http_timeout"])
        config_data["reconnection_interval"] = timing_config.get("reconnection_interval_seconds", config_data["reconnection_interval"])

        if not config_data["zhipu_api_key"]:
            logger.warning("ZhipuAI API key not found in configuration.")
        if not config_data["zhipu_model"]:
            logger.warning("ZhipuAI model name not found in configuration.")

    except FileNotFoundError:
        logger.warning(f"Configuration file {pyproject_file} not found! Using default settings.")
    except Exception as e:
        logger.error(f"Error parsing configuration file {pyproject_file}: {e}. Using default settings.", exc_info=True)

    logger.info(f"Loaded configuration: {config_data}")
    return config_data