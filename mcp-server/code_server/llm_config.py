import os
import toml
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# --- Configuration Constants ---
# Default values, can be overridden by config file
HEARTBEAT_INTERVAL_SECONDS = 60 # Check every 60 seconds (Adjusted back to original default)
HEARTBEAT_TIMEOUT_SECONDS = 180 # Disconnect after 180 seconds of no response
HTTP_TIMEOUT_SECONDS = 10 # Timeout for HTTP health checks
RECONNECTION_INTERVAL_SECONDS = 60 # Try reconnecting every 60 seconds

@dataclass
class LLMConfig:
    provider: str
    api_key: str
    model: str
    base_url: Optional[str] = None

def load_llm_config(config: Dict[str, Any]) -> LLMConfig:
    """Load LLM settings from configuration"""
    llm_config = config.get("tool", {}).get("llm", {})
    print(llm_config)
    # For backward compatibility, try using zhipu config if llm config is not found
    if not llm_config:
        zhipu_config = config.get("tool", {}).get("zhipu", {})
        if zhipu_config:
            return LLMConfig(
                provider="zhipuai",
                api_key=zhipu_config.get("openai_api_key"),
                model=zhipu_config.get("model")
            )
    
    return LLMConfig(
        provider=llm_config.get("provider", "zhipuai"),
        api_key=llm_config.get("api_key"),
        model=llm_config.get("model"),
        base_url=llm_config.get("base_url")
    )

def load_app_config(pyproject_file: Optional[str] = None) -> Dict[str, Any]:
    """Loads configuration from pyproject.toml."""
    if pyproject_file is None:
        current_dir = os.path.dirname(__file__)
        # Assumes config.py is in the same dir as main.py, and pyproject.toml is one level up
        pyproject_file = os.path.join(current_dir, "..",".." ,"pyproject.toml")
        # Adjust if your structure differs
        # pyproject_file = os.path.join(current_dir, "pyproject.toml")
        print(pyproject_file)
    # Default config valuesd
    config_data = {
        "heartbeat_interval": HEARTBEAT_INTERVAL_SECONDS,
        "heartbeat_timeout": HEARTBEAT_TIMEOUT_SECONDS,
        "http_timeout": HTTP_TIMEOUT_SECONDS,
        "reconnection_interval": RECONNECTION_INTERVAL_SECONDS,
    }

    try:
        logger.info(f"Loading configuration from: {pyproject_file}")
        with open(pyproject_file, "r", encoding="utf-8") as f:
            config = toml.load(f)
            print(f"config: {config}")
        # Load LLM configuration
        llm_config = load_llm_config(config)
        config_data["llm_config"] = llm_config

        # Load timing settings if present in config
        timing_config = config.get("tool", {}).get("timing", {})
        config_data["heartbeat_interval"] = timing_config.get("heartbeat_interval_seconds", config_data["heartbeat_interval"])
        config_data["heartbeat_timeout"] = timing_config.get("heartbeat_timeout_seconds", config_data["heartbeat_timeout"])
        config_data["http_timeout"] = timing_config.get("http_timeout_seconds", config_data["http_timeout"])
        config_data["reconnection_interval"] = timing_config.get("reconnection_interval_seconds", config_data["reconnection_interval"])

        if not llm_config.api_key:
            logger.warning(f"{llm_config.provider.capitalize()} API key not found in configuration.")
        if not llm_config.model:
            logger.warning(f"{llm_config.provider.capitalize()} model name not found in configuration.")

    except FileNotFoundError:
        logger.warning(f"Configuration file {pyproject_file} not found! Using default settings.")
    except Exception as e:
        logger.error(f"Error parsing configuration file {pyproject_file}: {e}. Using default settings.", exc_info=True)

    logger.info(f"Loaded configuration: {config_data}")
    return config_data