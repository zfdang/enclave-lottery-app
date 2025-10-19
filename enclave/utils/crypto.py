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


class EnclaveAttestation:
    """Handles enclave attestation and cryptographic operations"""
    
    def __init__(self):
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        self.public_key = self.private_key.public_key()
        
    def generate_attestation(self) -> str:
        """Generate enclave attestation document"""
        try:
            # In a real enclave, this would use the NSM (Nitro Security Module)
            # For simulation, we create a mock attestation document
            
            attestation_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "enclave_id": self._generate_enclave_id(),
                "pcrs": self._generate_mock_pcrs(),
                "public_key": self._get_public_key_pem(),
                "nonce": secrets.token_hex(32)
            }
            
            # Create signed attestation
            attestation_json = json.dumps(attestation_data, sort_keys=True)
            signature = self._sign_data(attestation_json.encode())
            
            final_attestation = {
                "attestation": attestation_data,
                "signature": base64.b64encode(signature).decode()
            }
            
            return base64.b64encode(json.dumps(final_attestation).encode()).decode()
            
        except Exception as e:
            logger.error(f"Error generating attestation: {e}")
            return ""
            
    def _generate_enclave_id(self) -> str:
        """Generate unique enclave identifier"""
        # In real implementation, this would be provided by the enclave
        return hashlib.sha256(f"lottery_enclave_{datetime.utcnow()}".encode()).hexdigest()[:16]
        
    def _generate_mock_pcrs(self) -> Dict[str, str]:
        """Generate mock Platform Configuration Registers (PCRs)"""
        # In real enclave, PCRs are provided by the NSM
        return {
            "PCR0": hashlib.sha256(b"lottery_app_image").hexdigest(),
            "PCR1": hashlib.sha256(b"linux_kernel").hexdigest(),
            "PCR2": hashlib.sha256(b"application_code").hexdigest(),
            "PCR3": hashlib.sha256(b"iam_role").hexdigest(),
            "PCR4": hashlib.sha256(b"instance_id").hexdigest(),
        }
        
    def _get_public_key_pem(self) -> str:
        """Get public key in PEM format"""
        pem = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return pem.decode()
        
    def _sign_data(self, data: bytes) -> bytes:
        """Sign data with private key"""
        signature = self.private_key.sign(
            data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return signature
        
    def verify_signature(self, data: bytes, signature: bytes) -> bool:
        """Verify signature with public key"""
        try:
            self.public_key.verify(
                signature,
                data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except Exception:
            return False
            
    def encrypt_data(self, data: bytes) -> bytes:
        """Encrypt data using AES"""
        # Generate random key and IV
        key = secrets.token_bytes(32)  # 256-bit key
        iv = secrets.token_bytes(16)   # 128-bit IV
        
        # Encrypt data
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        
        # Pad data to block size
        padded_data = self._pad_data(data)
        encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
        
        # Encrypt key with RSA
        encrypted_key = self.public_key.encrypt(
            key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        # Combine encrypted key, IV, and encrypted data
        return encrypted_key + iv + encrypted_data
        
    def decrypt_data(self, encrypted_data: bytes) -> bytes:
        """Decrypt data using AES"""
        # Extract components
        encrypted_key = encrypted_data[:256]  # RSA key size
        iv = encrypted_data[256:272]          # IV size
        ciphertext = encrypted_data[272:]     # Remaining data
        
        # Decrypt key with RSA
        key = self.private_key.decrypt(
            encrypted_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        # Decrypt data with AES
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(ciphertext) + decryptor.finalize()
        
        # Remove padding
        return self._unpad_data(padded_data)
        
    def _pad_data(self, data: bytes) -> bytes:
        """Add PKCS7 padding to data"""
        block_size = 16
        padding_length = block_size - (len(data) % block_size)
        padding = bytes([padding_length] * padding_length)
        return data + padding
        
    def _unpad_data(self, padded_data: bytes) -> bytes:
        """Remove PKCS7 padding from data"""
        padding_length = padded_data[-1]
        return padded_data[:-padding_length]


class SecureRandom:
    """Cryptographically secure random number generator"""
    
    @staticmethod
    def generate_random_int(min_val: int, max_val: int) -> int:
        """Generate cryptographically secure random integer"""
        return secrets.randbelow(max_val - min_val + 1) + min_val
        
    @staticmethod
    def generate_random_bytes(length: int) -> bytes:
        """Generate cryptographically secure random bytes"""
        return secrets.token_bytes(length)
        
    @staticmethod
    def generate_random_hex(length: int) -> str:
        """Generate cryptographically secure random hex string"""
        return secrets.token_hex(length)


def hash_data(data: bytes, algorithm: str = "sha256") -> str:
    """Hash data using specified algorithm"""
    if algorithm == "sha256":
        return hashlib.sha256(data).hexdigest()
    elif algorithm == "sha512":
        return hashlib.sha512(data).hexdigest()
    elif algorithm == "md5":
        return hashlib.md5(data).hexdigest()
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")


def constant_time_compare(a: bytes, b: bytes) -> bool:
    """Constant time comparison to prevent timing attacks"""
    if len(a) != len(b):
        return False
        
    result = 0
    for x, y in zip(a, b):
        result |= x ^ y
    return result == 0


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