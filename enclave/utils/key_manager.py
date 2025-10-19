"""Operator key validation and management utilities.

This module provides functions for validating Ethereum private keys,
deriving addresses, and verifying key-address pairs.
"""

import re
from typing import Tuple

from eth_account import Account
from utils.logger import get_logger

logger = get_logger(__name__)


def validate_eth_private_key_format(private_key: str) -> Tuple[bool, str]:
    """Validate Ethereum private key format.
    
    Expected format: 0x followed by 64 hexadecimal characters
    
    Args:
        private_key: Private key string to validate
        
    Returns:
        tuple: (is_valid, error_message)
            - is_valid: True if format is valid
            - error_message: Empty string if valid, error description if invalid
    """
    if not isinstance(private_key, str):
        return False, "Private key must be a string"
        
    if not private_key.startswith("0x"):
        return False, "Private key must start with '0x' prefix"
        
    if len(private_key) != 66:  # 0x + 64 hex chars
        return False, f"Private key must be 66 characters long (0x + 64 hex), got {len(private_key)}"
        
    # Check if remaining 64 characters are valid hex
    hex_part = private_key[2:]
    if not re.match(r'^[0-9a-fA-F]{64}$', hex_part):
        return False, "Private key must contain only hexadecimal characters after '0x'"
        
    return True, ""


def derive_address_from_private_key(private_key: str) -> str:
    """Derive Ethereum address from private key.
    
    Args:
        private_key: Ethereum private key (0x prefixed hex string)
        
    Returns:
        str: Derived Ethereum address (checksummed, 0x prefixed)
        
    Raises:
        ValueError: If private key is invalid
    """
    try:
        account = Account.from_key(private_key)
        return account.address
    except Exception as e:
        logger.error(f"Failed to derive address from private key: {e}")
        raise ValueError(f"Invalid private key: {e}")


def validate_operator_key(
    private_key: str, 
    expected_address: str
) -> Tuple[bool, str, str]:
    """Validate that operator private key matches expected address.
    
    This function performs complete validation:
    1. Checks private key format
    2. Derives address from private key
    3. Compares derived address with expected address (case-insensitive)
    
    Args:
        private_key: Operator private key to validate
        expected_address: Expected operator address from configuration
        
    Returns:
        tuple: (is_valid, derived_address, error_message)
            - is_valid: True if validation passed
            - derived_address: Address derived from private key (empty if derivation failed)
            - error_message: Empty if valid, error description if invalid
    """
    # Step 1: Validate format
    format_valid, format_error = validate_eth_private_key_format(private_key)
    if not format_valid:
        return False, "", format_error
        
    # Step 2: Derive address
    try:
        derived_address = derive_address_from_private_key(private_key)
    except ValueError as e:
        return False, "", str(e)
        
    # Step 3: Compare addresses (case-insensitive)
    if derived_address.lower() != expected_address.lower():
        error_msg = (
            f"Address mismatch: derived {derived_address} "
            f"but expected {expected_address}"
        )
        logger.warning(error_msg)
        return False, derived_address, error_msg
        
    logger.info(f"Operator key validated successfully for address {derived_address}")
    return True, derived_address, ""


def normalize_eth_address(address: str) -> str:
    """Normalize Ethereum address to checksummed format.
    
    Args:
        address: Ethereum address (with or without 0x prefix)
        
    Returns:
        str: Checksummed Ethereum address with 0x prefix
    """
    if not address.startswith("0x"):
        address = "0x" + address
    return Account.normalize_address(address)
