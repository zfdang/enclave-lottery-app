#!/usr/bin/env python3
"""Client script to inject operator private key into enclave lottery application.

This script fetches the TLS public key from the enclave, encrypts the operator
private key using ECIES, and sends it to the /api/set_operator_key endpoint.

Usage:
    # From command line argument
    python scripts/set_operator_key.py --url http://localhost:6080 --private-key 0x1234...
    
    # From environment variable
    export OPERATOR_PRIVATE_KEY=0x1234...
    python scripts/set_operator_key.py --url http://localhost:6080
    
    # Interactive input (most secure - not stored in shell history)
    python scripts/set_operator_key.py --url http://localhost:6080
    # You will be prompted to enter the private key

Security Notes:
    - The private key is encrypted with ECIES before transmission
    - Using environment variables or interactive input is more secure than command line args
    - Command line arguments may be visible in process lists
"""

import argparse
import base64
import getpass
import os
import sys
from typing import Optional

import requests


def validate_private_key_format(private_key: str) -> bool:
    """Validate that private key has correct format.
    
    Args:
        private_key: Private key to validate
        
    Returns:
        bool: True if format is valid
    """
    if not private_key.startswith("0x"):
        print("❌ Error: Private key must start with '0x'")
        return False
    if len(private_key) != 66:
        print(f"❌ Error: Private key must be 66 characters (0x + 64 hex), got {len(private_key)}")
        return False
    try:
        int(private_key, 16)
        return True
    except ValueError:
        print("❌ Error: Private key must be valid hexadecimal")
        return False


def get_private_key(args: argparse.Namespace) -> Optional[str]:
    """Get private key from various sources (args, env, or interactive).
    
    Priority:
    1. Command line argument (--private-key)
    2. Environment variable (OPERATOR_PRIVATE_KEY)
    3. Interactive input (secure, not stored in history)
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        str or None: Private key if obtained and valid, None otherwise
    """
    private_key = None
    
    # Try command line argument
    if args.private_key:
        print("📝 Using private key from command line argument")
        private_key = args.private_key
    # Try environment variable
    elif os.environ.get("OPERATOR_PRIVATE_KEY"):
        print("📝 Using private key from OPERATOR_PRIVATE_KEY environment variable")
        private_key = os.environ.get("OPERATOR_PRIVATE_KEY")
    # Interactive input
    else:
        print("🔐 Enter operator private key (input will be hidden):")
        private_key = getpass.getpass("Private key (0x...): ")
    
    if not private_key:
        print("❌ Error: No private key provided")
        return None
    
    private_key = private_key.strip()
    
    if not validate_private_key_format(private_key):
        return None
        
    return private_key


def fetch_public_key(url: str) -> Optional[dict]:
    """Fetch TLS public key from enclave API.
    
    Args:
        url: Base URL of the lottery API
        
    Returns:
        dict or None: Public key response if successful, None otherwise
    """
    endpoint = f"{url}/api/get_pub_key"
    print(f"📡 Fetching public key from {endpoint}...")
    
    try:
        response = requests.get(endpoint, timeout=10)
        response.raise_for_status()
        data = response.json()
        print(f"✅ Public key fetched successfully")
        print(f"   Curve: {data.get('curve')}")
        print(f"   Key size: {data.get('key_size')} bits")
        return data
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to fetch public key: {e}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error fetching public key: {e}")
        return None


def encrypt_private_key(private_key: str, public_key_hex: str) -> Optional[str]:
    """Encrypt private key with ECIES using the public key.
    
    Args:
        private_key: Operator private key to encrypt
        public_key_hex: TLS public key in hex format (SECP384R1 uncompressed)
        
    Returns:
        str or None: Base64-encoded encrypted data if successful, None otherwise
    """
    print("🔐 Encrypting private key with ECIES...")
    
    try:
        # Import ECIES implementation
        import secrets
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import hashes, hmac
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        
        plaintext = private_key.encode('utf-8')
        
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
        encrypted = ephemeral_public_key_bytes + nonce + ciphertext + hmac_tag
        
        # Base64 encode
        encrypted_b64 = base64.b64encode(encrypted).decode('utf-8')
        
        print(f"✅ Private key encrypted successfully ({len(encrypted)} bytes)")
        return encrypted_b64
        
    except ImportError as e:
        print(f"❌ Error: Required cryptography library not installed: {e}")
        print("   Install with: pip install cryptography")
        return None
    except Exception as e:
        print(f"❌ Failed to encrypt private key: {e}")
        print("   Make sure the enclave returned an uncompressed SECP384R1 public key (hex), typically starting with '04'.")
        print("   Expected format: 194 hex characters (04 + 96 chars x + 96 chars y)")
        return None
def inject_operator_key(url: str, encrypted_private_key: str) -> bool:
    """Send encrypted private key to the enclave API.
    
    Args:
        url: Base URL of the lottery API
        encrypted_private_key: Base64-encoded encrypted private key
        
    Returns:
        bool: True if injection successful, False otherwise
    """
    endpoint = f"{url}/api/set_operator_key"
    print(f"📡 Sending encrypted key to {endpoint}...")
    
    try:
        response = requests.post(
            endpoint,
            json={"encrypted_private_key": encrypted_private_key},
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        # Try to parse response as JSON
        try:
            data = response.json()
        except Exception:
            data = {}
        
        if response.status_code == 200:
            print("✅ Operator key set successfully!")
            print(f"   Operator address: {data.get('operator_address', 'N/A')}")
            print(f"   Message: {data.get('message', 'N/A')}")
            return True
        elif response.status_code == 403:
            print("⚠️  Operator key already set")
            print(f"   Address: {data.get('operator_address', 'N/A')}")
            print(f"   Error: {data.get('error', 'Already configured')}")
            return False
        elif response.status_code == 400:
            print("❌ Validation failed")
            print(f"   Error: {data.get('error', 'Bad request')}")
            if 'detail' in data:
                print(f"   Detail: {data['detail']}")
            if 'expected_address' in data:
                print(f"   Expected address: {data['expected_address']}")
            if 'derived_address' in data:
                print(f"   Derived address: {data['derived_address']}")
            if data.get('operator_key_set') is False:
                print("   💡 You can retry with the correct private key")
            return False
        else:
            print(f"❌ Request failed with status {response.status_code}")
            print(f"   Response: {data or response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to send request: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def main() -> int:
    """Main entry point.
    
    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    parser = argparse.ArgumentParser(
        description="Inject operator private key into enclave lottery application",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive input (most secure)
  %(prog)s --url http://localhost:6080
  
  # From environment variable
  export OPERATOR_PRIVATE_KEY=0x1234...
  %(prog)s --url http://localhost:6080
  
  # From command line (less secure)
  %(prog)s --url http://localhost:6080 --private-key 0x1234...
  
Security Notes:
  - Interactive input is recommended (not stored in shell history)
  - Environment variables are safer than command line arguments
  - The private key is encrypted with ECIES before transmission
        """
    )
    
    parser.add_argument(
        "--url",
        required=True,
        help="Base URL of the lottery API (e.g., http://localhost:6080)"
    )
    
    parser.add_argument(
        "--private-key",
        help="Operator private key (0x prefixed hex). If not provided, will use OPERATOR_PRIVATE_KEY env var or prompt for input."
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🔐 Enclave Lottery - Operator Key Injection Tool")
    print("=" * 60)
    
    # Step 1: Get private key
    private_key = get_private_key(args)
    if not private_key:
        return 1
    
    # Step 2: Fetch public key
    pub_key_data = fetch_public_key(args.url)
    if not pub_key_data:
        return 2
    
    public_key_hex = pub_key_data.get("public_key_hex")
    if not public_key_hex:
        print("❌ Error: No public_key_hex in response")
        return 3
    
    # Step 3: Encrypt private key
    encrypted_key = encrypt_private_key(private_key, public_key_hex)
    if not encrypted_key:
        return 4
    
    # Step 4: Inject encrypted key
    success = inject_operator_key(args.url, encrypted_key)
    
    print("=" * 60)
    if success:
        print("✅ Operation completed successfully")
        return 0
    else:
        print("❌ Operation failed")
        return 5


if __name__ == "__main__":
    sys.exit(main())
