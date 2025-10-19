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
    config_file = Path(__file__).parent.parent / "lottery.conf"
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

    # Normalize and apply sensible defaults for event manager (event_manager / polling)
    # event_manager top-level configuration (used at runtime)
    # If `enclave/lottery.conf` provides an `event_manager` section, treat those
    # values as repository-level defaults (they will be used only when explicit runtime
    # `event_manager` keys are not present or when env vars do not override them).
    file_eventmgr = config.get('event_manager', {}) or {}
    eventmgr = config.setdefault('event_manager', {})

    # Default intervals (seconds)
    # Use file-provided event_manager defaults when present, otherwise fall back to hardcoded defaults
    eventmgr.setdefault('contract_config_interval_sec', int(eventmgr.get('contract_config_interval_sec', file_eventmgr.get('contract_config_interval_sec', 10))))
    eventmgr.setdefault('round_and_participants_interval_sec', int(eventmgr.get('round_and_participants_interval_sec', file_eventmgr.get('round_and_participants_interval_sec', 2))))

    # Event polling options
    eventmgr.setdefault('event_source', eventmgr.get('event_source', file_eventmgr.get('event_source', 'eth_getLogs')))
    eventmgr.setdefault('start_block_offset', int(eventmgr.get('start_block_offset', file_eventmgr.get('start_block_offset', 500))))

    # Retention sizes
    eventmgr.setdefault('live_feed_max_entries', int(eventmgr.get('live_feed_max_entries', file_eventmgr.get('live_feed_max_entries', 1000))))
    eventmgr.setdefault('round_history_max', int(eventmgr.get('round_history_max', file_eventmgr.get('round_history_max', 100))))

    # Blockchain node / provider
    blockchain = config.setdefault('blockchain', {})
    blockchain.setdefault('rpc_url', blockchain.get('rpc_url', os.environ.get('BLOCKCHAIN_RPC_URL', 'https://base-sepolia.drpc.org/')))
    
    logger.info(f"Configuration after applying environment overrides: {json.dumps(config, indent=2)}")
    return config


def save_config(config: Dict[str, Any], config_file: str = None):
    """Save configuration to file"""
    if not config_file:
        config_file = Path(__file__).parent.parent / "lottery.conf"
    
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