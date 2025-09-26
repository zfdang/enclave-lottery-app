"""
Admin Configuration Management
Configuration for admin tools and deployment scripts
"""

import json
from pathlib import Path
from typing import Dict, Any

def load_publisher_config() -> Dict[str, Any]:
    """Load publisher configuration from publisher.conf (required)"""
    config_file = Path(__file__).parent / "publisher.conf"
    
    if not config_file.exists():
        print(f"❌ Publisher configuration file not found: {config_file}")
        print(f"💡 Please create {config_file} based on publisher.conf.example")
        print(f"   Example: cp publisher.conf.example publisher.conf")
        exit(1)
    
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        print(f"📝 Loaded publisher configuration from {config_file}")
        return config
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in publisher configuration file {config_file}")
        print(f"💡 Please check the JSON syntax in {config_file}")
        print(f"   Error details: {e}")
        exit(1)
    except Exception as e:
        print(f"❌ Error loading publisher configuration from {config_file}")
        print(f"💡 Please check file permissions and format")
        print(f"   Error details: {e}")
        exit(1)


def load_sparsity_config() -> Dict[str, Any]:
    """Load sparsity configuration from sparsity.conf (required)"""
    config_file = Path(__file__).parent / "sparsity.conf"
    
    if not config_file.exists():
        print(f"❌ Sparsity configuration file not found: {config_file}")
        print(f"💡 Please create {config_file} based on sparsity.conf.example")
        print(f"   Example: cp sparsity.conf.example sparsity.conf")
        exit(1)
    
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        print(f"📝 Loaded sparsity configuration from {config_file}")
        return config
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in sparsity configuration file {config_file}")
        print(f"💡 Please check the JSON syntax in {config_file}")
        print(f"   Error details: {e}")
        exit(1)
    except Exception as e:
        print(f"❌ Error loading sparsity configuration from {config_file}")
        print(f"💡 Please check file permissions and format")
        print(f"   Error details: {e}")
        exit(1)


def load_init_contract_config() -> Dict[str, Any]:
    """Load init-contract configuration from init-contract.conf (optional)

    This file is optional; when present it provides defaults for the
    init-contract script (rpc_url, chain_id, publisher/sparsity/operator info).
    """
    config_file = Path(__file__).parent / "init-contract.conf"

    if not config_file.exists():
        # Not required; return empty dict to allow CLI overrides
        return {}

    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        print(f"📝 Loaded init-contract configuration from {config_file}")
        return config
    except json.JSONDecodeError as e:
        print(f"⚠️  Invalid JSON in init-contract configuration file {config_file}")
        print(f"💡 Please check the JSON syntax in {config_file}")
        print(f"   Error details: {e}")
        return {}
    except Exception as e:
        print(f"⚠️  Error loading init-contract configuration from {config_file}: {e}")
        print(f"💡 Please check file permissions and format")
        return {}