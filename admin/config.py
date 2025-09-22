"""
Admin Configuration Management
Configuration for admin tools and deployment scripts
"""

import json
from pathlib import Path
from typing import Dict, Any


def load_admin_config() -> Dict[str, Any]:
    """Load admin configuration with defaults"""
    config = {
        'blockchain': {
            'rpc_url': 'http://localhost:8545',
            'private_key': '0x2a871d0798f97d79848a013d4936a73bf4cc922c825d33c1cf7073dff6d409c6',
            'chain_id': 31337
        },
        'contract': {
            'commission_rate': 500,  # basis points (5%)
            'min_bet': 0.01,  # ETH
            'betting_duration': 900,  # seconds (15 minutes)
            'draw_delay': 90  # seconds (1.5 minutes)
        },
        'output': {
            'config_output': 'admin/operator.conf',
            'deployment_output': 'admin/deployment.json'
        }
    }
    
    # Try to load from admin config file
    config_file = Path(__file__).parent / "admin.conf"
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                file_config = json.load(f)
                # Deep merge configuration
                for section, values in file_config.items():
                    if section in config and isinstance(config[section], dict):
                        config[section].update(values)
                    else:
                        config[section] = values
                print(f"📝 Loaded admin configuration from {config_file}")
        except Exception as e:
            print(f"⚠️  Error loading admin config file: {e}")
    
    return config


def save_admin_config(config: Dict[str, Any], config_file: str = None):
    """Save admin configuration to file"""
    if not config_file:
        config_file = Path(__file__).parent / "admin.conf"
    
    try:
        config_file = Path(config_file)
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
            
        print(f"✅ Admin configuration saved to {config_file}")
    except Exception as e:
        print(f"❌ Error saving admin configuration: {e}")


def get_admin_config_value(config: Dict[str, Any], key_path: str, default=None):
    """Get admin configuration value by dot-separated key path"""
    keys = key_path.split('.')
    value = config
    
    try:
        for key in keys:
            value = value[key]
        return value
    except (KeyError, TypeError):
        return default