"""
Cryptographic utilities and enclave attestation
"""

import base64
import hashlib
import json
import logging
import secrets
from datetime import datetime
from typing import Dict, Optional

from utils.logger import get_logger

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding, ec
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

logger = get_logger(__name__)

class TLSKeyPair:
    """TLS SECP384R1 key pair for secure operator key injection.
    
    This key pair is used to encrypt the operator private key during injection.
    The public key is exposed via API and included in attestation documents.
    The private key is used to decrypt the encrypted operator key.
    
    Uses SECP384R1 curve with ECIES-style encryption (ECDH + AES-256-GCM).
    """
    
    def __init__(self):
        """Generate a new SECP384R1 key pair."""
        self.private_key = ec.generate_private_key(
            ec.SECP384R1(), 
            default_backend()
        )
        self.public_key = self.private_key.public_key()
        logger.info("Generated new TLS SECP384R1 key pair for secure key injection")
        
    def get_public_key_pem(self) -> str:
        """Get public key in PEM format.
        
        Returns:
            str: PEM-encoded public key
        """
        pem_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return pem_bytes.decode('utf-8')
        
    def get_public_key_hex(self) -> str:
        """Get public key in uncompressed hex format (04 prefix + x + y coordinates).
        
        Returns:
            str: Hex-encoded public key (97 bytes for SECP384R1: 1 byte prefix + 48 bytes x + 48 bytes y)
        """
        public_numbers = self.public_key.public_numbers()
        x_bytes = public_numbers.x.to_bytes(48, byteorder='big')
        y_bytes = public_numbers.y.to_bytes(48, byteorder='big')
        # Uncompressed format: 0x04 + x + y
        uncompressed = b'\x04' + x_bytes + y_bytes
        return uncompressed.hex()
        
    def decrypt_ecies(self, encrypted_data: bytes) -> bytes:
        """Decrypt data encrypted with ECIES using this key pair.
        
        ECIES encryption format:
        - Ephemeral public key (97 bytes for SECP384R1 uncompressed)
        - Nonce (12 bytes for AES-GCM)
        - AES-256-GCM ciphertext + tag
        - HMAC-SHA256 (32 bytes)
        
        Args:
            encrypted_data: ECIES encrypted data
            
        Returns:
            bytes: Decrypted plaintext
            
        Raises:
            Exception: If decryption fails
        """
        try:
            from utils.ecies_secp384r1 import decrypt_ecies
            
            # Get private key as bytes
            private_key_bytes = self.private_key.private_numbers().private_value.to_bytes(48, byteorder='big')
            
            # Decrypt using ECIES
            plaintext = decrypt_ecies(private_key_bytes, encrypted_data)
            
            return plaintext
            
        except Exception as e:
            logger.error(f"ECIES decryption failed: {e}")
            raise
            raise
            
    def get_key_info(self) -> Dict[str, any]:
        """Get key pair information for API responses.
        
        Returns:
            dict: Key information including curve, size, and usage
        """
        return {
            "curve": "secp384r1",
            "key_size": 384,
            "usage": "Use this public key to encrypt operator private key with ECIES"
        }