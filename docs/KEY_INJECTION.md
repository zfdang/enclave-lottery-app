# Secure Operator Key Injection

This document explains the secure key injection mechanism for the enclave lottery application.

## Overview

The lottery application uses a two-key-pair architecture to ensure secure operation:

1. **TLS Key Pair (SECP384R1)** - For encrypting the operator private key during injection
2. **Operator Key Pair (Ethereum)** - For signing blockchain transactions

This design ensures that the operator's private key can be securely injected into the enclave after startup, without storing it in configuration files or environment variables.

## Architecture

### TLS Key Pair (SECP384R1)

**Purpose**: Encrypt the operator private key during transmission using ECIES

**Cryptography**: Uses the `cryptography` library with ECDH + AES-256-GCM + HMAC-SHA256

**Lifecycle**:
- Generated automatically on application startup
- Stored only in memory (never persisted to disk)
- New key pair generated on each restart
- Public key exposed via `/api/get_pub_key` endpoint
- Public key included in attestation document for verification

**Technical Details**:
- Curve: SECP384R1 (384-bit elliptic curve)
- Encryption: ECIES (Elliptic Curve Integrated Encryption Scheme)
- Key format: 
  - Public key PEM: Standard PEM format for easy use
  - Public key Hex: Uncompressed format (04 + x + y coordinates)

### Operator Key Pair (Ethereum)

**Purpose**: Sign blockchain transactions (e.g., `drawWinner`)

**Lifecycle**:
- Expected address configured in `lottery.conf` → `blockchain.operator_address`
- Private key NOT stored in config (empty string)
- Private key injected via `/api/set_operator_key` endpoint
- Address validation performed before accepting private key
- Can only be set once per application instance

**Security**:
- Private key transmitted encrypted with ECIES
- Address derived from private key must match configured address
- Stored only in memory after successful injection
- Required for transaction signing operations

## Key Injection Flow

```
┌─────────────┐
│   Enclave   │
│   Startup   │
└──────┬──────┘
       │
       ├─► Generate TLS SECP384R1 Key Pair
       ├─► Read operator_address from lottery.conf
       ├─► Initialize BlockchainClient (no private key)
       └─► Start Web Server
              │
              ▼
       ┌─────────────────┐
       │ Operator Key    │
       │ Not Set Yet     │
       │ (Waiting...)    │
       └─────────────────┘
              │
              ▼
    ┌──────────────────────┐
    │  External Client     │
    │  (Key Injection)     │
    └──────────────────────┘
              │
              ├─► GET /api/get_pub_key
              │   └─► Receive TLS public key
              │
              ├─► Encrypt operator private key with ECIES
              │   └─► Using TLS public key
              │
              ├─► POST /api/set_operator_key
              │   └─► Send encrypted private key
              │
              ▼
       ┌─────────────────┐
       │   Enclave       │
       │   Validates     │
       └────────┬────────┘
                │
                ├─► Decrypt with TLS private key
                ├─► Validate format (0x + 64 hex)
                ├─► Derive address from private key
                ├─► Compare with configured address
                │
                ├─► ✅ Match? → Set operator key (LOCKED)
                └─► ❌ Mismatch? → Reject (can retry)
```

## API Endpoints

### GET `/api/get_pub_key`

Retrieve the TLS public key for encrypting operator private key.

**Response**:
```json
{
  "public_key_pem": "-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----",
  "public_key_hex": "04a1b2c3d4e5...",
  "curve": "secp384r1",
  "key_size": 384,
  "usage": "Use this public key to encrypt operator private key with ECIES",
  "timestamp": 1729267200000
}
```

### POST `/api/set_operator_key`

Inject the encrypted operator private key.

**Request**:
```json
{
  "encrypted_private_key": "base64_encoded_ecies_encrypted_data"
}
```

**Success Response (200)**:
```json
{
  "success": true,
  "operator_address": "0x25fBB15755ae6c3E18e17E1D77859D2b3c6560CE",
  "message": "Operator key set successfully",
  "timestamp": 1729267200000
}
```

**Error Responses**:

**Already Set (403)**:
```json
{
  "success": false,
  "error": "Operator key already set. Cannot change once configured.",
  "operator_address": "0x25fBB15755ae6c3E18e17E1D77859D2b3c6560CE",
  "timestamp": 1729267200000
}
```

**Address Mismatch (400)**:
```json
{
  "success": false,
  "error": "Address mismatch",
  "expected_address": "0x25fBB15755ae6c3E18e17E1D77859D2b3c6560CE",
  "derived_address": "0xABCDEF...",
  "operator_key_set": false,
  "message": "The private key does not match the configured operator address. You can retry with correct key."
}
```

**Decryption Failed (400)**:
```json
{
  "success": false,
  "error": "Failed to decrypt private key",
  "detail": "ECIES decryption error: ...",
  "operator_key_set": false,
  "message": "You can retry with correct encryption"
}
```

## Usage

### Using the Client Script

The provided `scripts/set_operator_key.py` script handles the complete injection process.

**Method 1: Interactive Input (Most Secure)**
```bash
python scripts/set_operator_key.py --url http://localhost:6080
# You will be prompted to enter private key (input hidden)
```

**Method 2: Environment Variable**
```bash
export OPERATOR_PRIVATE_KEY=0x1234567890abcdef...
python scripts/set_operator_key.py --url http://localhost:6080
```

**Method 3: Command Line Argument (Less Secure)**
```bash
python scripts/set_operator_key.py \
  --url http://localhost:6080 \
  --private-key 0x1234567890abcdef...
```

**Script Dependencies**:
```bash
pip install requests cryptography
```

### Manual Process

If you need to implement the injection manually:

```python
import base64
import requests
import ecies

# Step 1: Fetch public key
response = requests.get("http://localhost:6080/api/get_pub_key")
pub_key_hex = response.json()["public_key_hex"]

# Step 2: Encrypt private key
public_key_bytes = bytes.fromhex(pub_key_hex)
private_key = "0x1234567890abcdef..."
encrypted = ecies.encrypt(public_key_bytes, private_key.encode('utf-8'))
encrypted_b64 = base64.b64encode(encrypted).decode('utf-8')

# Step 3: Inject
response = requests.post(
    "http://localhost:6080/api/set_operator_key",
    json={"encrypted_private_key": encrypted_b64}
)
print(response.json())
```

## Configuration

### lottery.conf

The operator address must be configured in `lottery.conf`:

```json
{
  "blockchain": {
    "operator_address": "0x25fBB15755ae6c3E18e17E1D77859D2b3c6560CE",
    "operator_private_key": "",
    ...
  }
}
```

**Important**:
- `operator_address`: Required, set to expected operator address
- `operator_private_key`: Leave empty (will be injected via API)

## Security Considerations

### Transport Security

1. **ECIES Encryption**: Private key is encrypted using ECIES with SECP384R1 public key
2. **One-Time Key**: TLS key pair is regenerated on each restart
3. **Address Validation**: Derived address must match configured address

### Attack Vectors & Mitigations

| Attack | Mitigation |
|--------|-----------|
| Man-in-the-middle | Use HTTPS/TLS for API communication in production |
| Replay attacks | TLS key pair changes on restart; encrypted data becomes invalid |
| Brute force | SECP384R1 provides 192-bit security level |
| Key extraction | Private keys stored only in memory, never written to disk |
| Wrong key injection | Address validation prevents accepting incorrect keys |
| Multiple injections | Key can only be set once; subsequent attempts fail with 403 |

### Best Practices

1. **Use Interactive Input**: Avoids storing private key in shell history
2. **Clear Environment Variables**: If using env vars, clear them after injection
   ```bash
   export OPERATOR_PRIVATE_KEY=0x...
   python scripts/set_operator_key.py --url http://localhost:6080
   unset OPERATOR_PRIVATE_KEY
   ```
3. **Verify Attestation**: Check attestation document to ensure TLS public key is from trusted enclave
4. **Use HTTPS**: Always use HTTPS in production environments
5. **Rotate Keys**: If enclave is compromised, restart with new TLS key pair
6. **Monitor Logs**: Watch for failed injection attempts (potential attacks)

## Operational Procedures

### Initial Setup

1. Deploy enclave with `operator_address` configured in `lottery.conf`
2. Start the application (generates new TLS key pair)
3. Optionally verify attestation document contains correct TLS public key
4. Run injection script to set operator private key
5. Verify operator key set successfully
6. Application is now ready to sign transactions

### Key Rotation

To rotate the operator key:

1. Stop the application
2. Update `operator_address` in `lottery.conf` to new address
3. Restart application (generates new TLS key pair)
4. Inject new operator private key matching new address
5. Verify successful injection

### Troubleshooting

**Problem**: "Address mismatch" error

**Solution**: 
- Verify the private key matches the configured `operator_address`
- Check `lottery.conf` has correct address
- You can retry with correct private key (not locked out)

**Problem**: "Operator key already set" error

**Solution**:
- Key was already injected successfully
- If you need to change it, restart the application

**Problem**: "Failed to decrypt private key" error

**Solution**:
- Ensure you're using the current TLS public key (fetch again)
- Verify ECIES encryption is correct (SECP384R1, 194 hex chars)
- Check cryptography library is installed: `pip install cryptography`
- You can retry with correct encryption

## Verification

### Verify TLS Public Key in Attestation

```bash
curl http://localhost:6080/api/attestation | jq '.user_data' | base64 -d | jq '.'
```

Expected output includes:
```json
{
  "lottery_contract": "0x...",
  "operator_address": "0x...",
  "tls_public_key_hex": "04a1b2c3...",
  ...
}
```

### Verify Operator Key Status

```bash
curl http://localhost:6080/api/status | jq '.blockchain'
```

Look for operator address in the response.

## Development Notes

### Testing

For development/testing, you can still use the old method by setting `operator_private_key` directly in `lottery.conf`. This provides backward compatibility:

```json
{
  "blockchain": {
    "operator_address": "0x...",
    "operator_private_key": "0x...",
  }
}
```

However, for production enclaves, leave `operator_private_key` empty and use the injection mechanism.

### Dependencies

- Python 3.9+
- `cryptography>=41.0.0` - Cryptographic primitives (ECIES implementation)
- `eth-account>=0.13.0` - Ethereum address derivation
- `requests` - HTTP client (for injection script)

### ECIES Implementation

Custom ECIES implementation using the `cryptography` library:
- **Module**: `enclave/utils/ecies_secp384r1.py`
- **Algorithm**: ECDH + AES-256-GCM + HMAC-SHA256
- **Curve**: SECP384R1 (384-bit security)
- **Format**: ephemeral_pubkey (97B) || nonce (12B) || ciphertext+tag || hmac (32B)

## References

- [ECIES Wikipedia](https://en.wikipedia.org/wiki/Integrated_Encryption_Scheme)
- [SECP384R1 Curve](https://neuromancer.sk/std/secg/secp384r1)
- [AWS Nitro Enclaves](https://aws.amazon.com/ec2/nitro/nitro-enclaves/)
- [Python Cryptography Library](https://cryptography.io/)
