"""
ECIES encryption/decryption for SECP384R1 using cryptography library.

This module provides ECIES (Elliptic Curve Integrated Encryption Scheme) implementation
compatible with SECP384R1 curve using the cryptography library.

Format:
    Encrypted data = ephemeral_pubkey (97 bytes) || nonce (12 bytes) || ciphertext+tag || hmac (32 bytes)
    
Components:
    - Ephemeral public key: 97 bytes uncompressed (0x04 + 48 bytes x + 48 bytes y)
    - Nonce: 12 bytes for AES-GCM
    - Ciphertext: Variable length (encrypted plaintext + 16 byte GCM tag)
    - HMAC: 32 bytes SHA256 HMAC over (ephemeral_pubkey || nonce || ciphertext+tag)
"""

import secrets
from typing import Tuple

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, hmac
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


def encrypt_ecies(public_key_hex: str, plaintext: bytes) -> bytes:
    """Encrypt data using ECIES with SECP384R1 public key.
    
    Args:
        public_key_hex: Hex-encoded uncompressed public key (194 hex chars = 97 bytes)
        plaintext: Data to encrypt
        
    Returns:
        bytes: Encrypted data (ephemeral_pubkey || nonce || ciphertext+tag || hmac)
        
    Raises:
        ValueError: If public key format is invalid
    """
    # Parse public key
    public_key_bytes = bytes.fromhex(public_key_hex)
    if len(public_key_bytes) != 97 or public_key_bytes[0] != 0x04:
        raise ValueError("Invalid public key format. Expected 97 bytes uncompressed (0x04 + x + y)")
    
    x = int.from_bytes(public_key_bytes[1:49], byteorder='big')
    y = int.from_bytes(public_key_bytes[49:97], byteorder='big')
    
    recipient_public_key = ec.EllipticCurvePublicNumbers(
        x, y, ec.SECP384R1()
    ).public_key(default_backend())
    
    # Generate ephemeral key pair
    ephemeral_private_key = ec.generate_private_key(ec.SECP384R1(), default_backend())
    ephemeral_public_key = ephemeral_private_key.public_key()
    
    # Serialize ephemeral public key
    ephemeral_public_numbers = ephemeral_public_key.public_numbers()
    ephemeral_x = ephemeral_public_numbers.x.to_bytes(48, byteorder='big')
    ephemeral_y = ephemeral_public_numbers.y.to_bytes(48, byteorder='big')
    ephemeral_public_key_bytes = b'\x04' + ephemeral_x + ephemeral_y
    
    # Perform ECDH to derive shared secret
    shared_key = ephemeral_private_key.exchange(ec.ECDH(), recipient_public_key)
    
    # Derive AES key using HKDF
    kdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b'ecies-aes-key',
    )
    aes_key = kdf.derive(shared_key)
    
    # Encrypt with AES-256-GCM
    aesgcm = AESGCM(aes_key)
    nonce = secrets.token_bytes(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    
    # Compute HMAC over ephemeral_pubkey || nonce || ciphertext
    # Use recipient's public key as HMAC key (derived from shared secret for better security)
    kdf_hmac = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b'ecies-hmac-key',
    )
    hmac_key = kdf_hmac.derive(shared_key)
    
    h = hmac.HMAC(hmac_key, hashes.SHA256())
    h.update(ephemeral_public_key_bytes + nonce + ciphertext)
    hmac_tag = h.finalize()
    
    # Combine all components
    encrypted_data = ephemeral_public_key_bytes + nonce + ciphertext + hmac_tag
    
    return encrypted_data


def decrypt_ecies(private_key_bytes: bytes, encrypted_data: bytes) -> bytes:
    """Decrypt ECIES encrypted data using SECP384R1 private key.
    
    Args:
        private_key_bytes: 48-byte private key in big-endian format
        encrypted_data: Encrypted data (ephemeral_pubkey || nonce || ciphertext+tag || hmac)
        
    Returns:
        bytes: Decrypted plaintext
        
    Raises:
        ValueError: If encrypted data format is invalid
        Exception: If HMAC verification or decryption fails
    """
    # Extract components
    min_length = 97 + 12 + 16 + 32  # ephemeral_pubkey + nonce + min_ciphertext + hmac
    if len(encrypted_data) < min_length:
        raise ValueError(f"Encrypted data too short. Expected at least {min_length} bytes, got {len(encrypted_data)}")
    
    ephemeral_public_key_bytes = encrypted_data[:97]
    nonce = encrypted_data[97:109]
    hmac_tag = encrypted_data[-32:]
    ciphertext = encrypted_data[109:-32]
    
    # Parse recipient's private key
    private_value = int.from_bytes(private_key_bytes, byteorder='big')
    private_key = ec.derive_private_key(private_value, ec.SECP384R1(), default_backend())
    
    # Parse ephemeral public key
    if ephemeral_public_key_bytes[0] != 0x04:
        raise ValueError("Invalid ephemeral public key format")
    
    x = int.from_bytes(ephemeral_public_key_bytes[1:49], byteorder='big')
    y = int.from_bytes(ephemeral_public_key_bytes[49:97], byteorder='big')
    
    ephemeral_public_key = ec.EllipticCurvePublicNumbers(
        x, y, ec.SECP384R1()
    ).public_key(default_backend())
    
    # Perform ECDH to derive shared secret
    shared_key = private_key.exchange(ec.ECDH(), ephemeral_public_key)
    
    # Derive HMAC key and verify
    kdf_hmac = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b'ecies-hmac-key',
    )
    hmac_key = kdf_hmac.derive(shared_key)
    
    h = hmac.HMAC(hmac_key, hashes.SHA256())
    h.update(ephemeral_public_key_bytes + nonce + ciphertext)
    h.verify(hmac_tag)
    
    # Derive AES key using HKDF
    kdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b'ecies-aes-key',
    )
    aes_key = kdf.derive(shared_key)
    
    # Decrypt with AES-256-GCM
    aesgcm = AESGCM(aes_key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    
    return plaintext
