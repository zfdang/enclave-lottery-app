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
    config = {
        'server': {
            'host': '0.0.0.0',
            'port': 8080
        },
        'lottery': {
            'draw_interval_minutes': 10,
            'minimum_interval_minutes': 3,
            'betting_cutoff_minutes': 1,
            'single_bet_amount': '0.01',
            'max_bets_per_user': 100
        },
        'blockchain': {
            'rpc_url': 'http://localhost:8545',
            'chain_id': 1337,
            'contract_address': None,
            'private_key': None
        },
        'enclave': {
            'vsock_port': 5000,
            'attestation_enabled': True
        }
    }
    
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
    
    # Override with environment variables
    config = _apply_env_overrides(config)
    
    return config


def _apply_env_overrides(config: Dict[str, Any]) -> Dict[str, Any]:
    """Apply environment variable overrides to configuration"""
    
    # Server configuration
    if os.getenv('LOTTERY_SERVER_HOST'):
        config['server']['host'] = os.getenv('LOTTERY_SERVER_HOST')
    if os.getenv('LOTTERY_SERVER_PORT'):
        config['server']['port'] = int(os.getenv('LOTTERY_SERVER_PORT'))
    
    # Lottery configuration (minutes-only)
    if os.getenv('LOTTERY_DRAW_INTERVAL_MINUTES'):
        config['lottery']['draw_interval_minutes'] = int(os.getenv('LOTTERY_DRAW_INTERVAL_MINUTES'))
    if os.getenv('LOTTERY_MINIMUM_INTERVAL_MINUTES'):
        config['lottery']['minimum_interval_minutes'] = int(os.getenv('LOTTERY_MINIMUM_INTERVAL_MINUTES'))
    if os.getenv('LOTTERY_BETTING_CUTOFF_MINUTES'):
        config['lottery']['betting_cutoff_minutes'] = int(os.getenv('LOTTERY_BETTING_CUTOFF_MINUTES'))
    if os.getenv('LOTTERY_SINGLE_BET_AMOUNT'):
        config['lottery']['single_bet_amount'] = os.getenv('LOTTERY_SINGLE_BET_AMOUNT')
    if os.getenv('LOTTERY_MAX_BETS_PER_USER'):
        config['lottery']['max_bets_per_user'] = int(os.getenv('LOTTERY_MAX_BETS_PER_USER'))
    
    # Blockchain configuration
    if os.getenv('BLOCKCHAIN_RPC_URL'):
        config['blockchain']['rpc_url'] = os.getenv('BLOCKCHAIN_RPC_URL')
    if os.getenv('BLOCKCHAIN_CHAIN_ID'):
        config['blockchain']['chain_id'] = int(os.getenv('BLOCKCHAIN_CHAIN_ID'))
    if os.getenv('BLOCKCHAIN_CONTRACT_ADDRESS'):
        config['blockchain']['contract_address'] = os.getenv('BLOCKCHAIN_CONTRACT_ADDRESS')
    if os.getenv('BLOCKCHAIN_PRIVATE_KEY'):
        config['blockchain']['private_key'] = os.getenv('BLOCKCHAIN_PRIVATE_KEY')
    
    # Enclave configuration
    if os.getenv('ENCLAVE_VSOCK_PORT'):
        config['enclave']['vsock_port'] = int(os.getenv('ENCLAVE_VSOCK_PORT'))
    if os.getenv('ENCLAVE_ATTESTATION_ENABLED'):
        config['enclave']['attestation_enabled'] = os.getenv('ENCLAVE_ATTESTATION_ENABLED').lower() == 'true'
    
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