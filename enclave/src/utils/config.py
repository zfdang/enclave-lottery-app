"""
Configuration Management
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


def load_config() -> Dict[str, Any]:
    """Load configuration from files and environment variables"""
    config = {}
    
    # Try to load from config file
    config_file = Path(__file__).parent.parent.parent / "config" / "enclave.conf"
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                file_config = json.load(f)
                config.update(file_config)
                logger.info(f"Loaded configuration from {config_file}")
        except Exception as e:
            logger.error(f"Error loading config file: {e}")
    else:
        logger.warning(f"Config file {config_file} not found. Will only use environment variables.")

    # Override with environment variables, defined in .env
    config = _apply_env_overrides(config)
    
    # show config again
    logger.info(f"Configuration after applying environment overrides: {json.dumps(config, indent=2)}")

    return config


def _apply_env_overrides(config: Dict[str, Any]) -> Dict[str, Any]:
    """Apply environment variable overrides to configuration"""
    for key, value in os.environ.items():
        # Convert key from ENV_VAR_NAME to section.key format
        if key.startswith("LOTTERY_"):
            section = "lottery"
            key = key[len("LOTTERY_"):].lower()
        elif key.startswith("BLOCKCHAIN_"):
            section = "blockchain"
            key = key[len("BLOCKCHAIN_"):].lower()
        elif key.startswith("ENCLAVE_"):
            section = "enclave"
            key = key[len("ENCLAVE_"):].lower()
        elif key.startswith("SERVER_"):
            section = "server"
            key = key[len("SERVER_"):].lower()
        elif key.startswith("APP_"):
            section = "app"
            key = key[len("APP_"):].lower()
        else:
            continue

        config.setdefault(section, {})[key] = value
        # logger.info(f"Overridden config '{section}.{key}' with env var '{key}'")

    return config


def save_config(config: Dict[str, Any], config_file: str = None):
    """Save configuration to file"""
    if not config_file:
        config_file = Path(__file__).parent.parent.parent / "config" / "enclave.conf"
    
    try:
        config_file = Path(config_file)
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
            
        logger.info(f"Configuration saved to {config_file}")
    except Exception as e:
        logger.error(f"Error saving configuration: {e}")


def get_config_value(config: Dict[str, Any], key_path: str, default=None):
    """Get configuration value by dot-separated key path"""
    keys = key_path.split('.')
    value = config
    
    try:
        for key in keys:
            value = value[key]
        return value
    except (KeyError, TypeError):
        return default