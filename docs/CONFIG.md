# Configuration Management Guide

This document describes the configuration management system used by the Enclave Lottery App.

## Configuration System Overview

The project uses a three-tier configuration priority system:

1. Hardcoded defaults (lowest priority)
2. Configuration file (`enclave/config/enclave.conf`) (medium priority)
3. Environment variables (highest priority)

## Configuration File Structure

### 1. Configuration file (`enclave/config/enclave.conf`)

This is a JSON file that contains default settings:

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 8080
  },
  "lottery": {
    "draw_interval_minutes": 5,
    "minimum_interval_minutes": 2,
    "betting_cutoff_minutes": 1,
    "single_bet_amount": "0.01",
    "max_bets_per_user": 10
  },
  "blockchain": {
    "rpc_url": "http://localhost:8545",
    "chain_id": 31337,
    "contract_address": "",
    "private_key": "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
  },
  "enclave": {
    "vsock_port": 5005,
    "attestation_enabled": false
  }
}
```

### 2. Environment variable file (`.env`)

Copy `.env.example` to `.env` and set your actual values:

```bash
cp .env.example .env
```

Then edit the `.env` file and set your real configuration values.

## Supported Environment Variables

### Server Configuration

| Variable | Legacy name | Description | Default |
|----------|-------------|-------------|---------|
| `SERVER_HOST` | `LOTTERY_SERVER_HOST` | Server bind address | `0.0.0.0` |
| `SERVER_PORT` | `LOTTERY_SERVER_PORT` | Server port | `8080` |

### Lottery Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `LOTTERY_DRAW_INTERVAL_MINUTES` | Draw interval (minutes) | `5` |
| `LOTTERY_MINIMUM_INTERVAL_MINUTES` | Minimum interval (minutes) | `2` |
| `LOTTERY_BETTING_CUTOFF_MINUTES` | Betting cutoff (minutes) | `1` |
| `LOTTERY_SINGLE_BET_AMOUNT` | Single bet amount (ETH) | `0.01` |
| `LOTTERY_MAX_BETS_PER_USER` | Max bets per user | `10` |

### Blockchain Configuration

| Variable | Legacy name | Description | Default |
|----------|-------------|-------------|---------|
| `ETHEREUM_RPC_URL` | `BLOCKCHAIN_RPC_URL` | Ethereum RPC URL | `http://localhost:8545` |
| `CHAIN_ID` | `BLOCKCHAIN_CHAIN_ID` | Chain ID | `31337` |
| `CONTRACT_ADDRESS` | `BLOCKCHAIN_CONTRACT_ADDRESS` | Contract address | `""` |
| `PRIVATE_KEY` | `BLOCKCHAIN_PRIVATE_KEY` | Private key | Test private key |

### Enclave Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `ENCLAVE_VSOCK_PORT` | VSock port | `5005` |
| `ENCLAVE_ATTESTATION_ENABLED` | Enable attestation | `false` |

### Frontend Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `REACT_APP_API_URL` | API URL | `http://localhost:8080` |
| `REACT_APP_WEBSOCKET_URL` | WebSocket URL | `ws://localhost:8080/ws` |

## Configuration Usage

### Development Environment

```bash
# 1. Copy the template
cp .env.example .env

# 2. Edit configuration
nano .env

# 3. Export required environment variables (optional)
export ETHEREUM_RPC_URL="http://localhost:8545"
export PRIVATE_KEY="your_development_private_key"

# 4. Run the application
python enclave/src/main.py
```

### Production Environment

Use environment variables in production instead of a `.env` file:

```bash
# Set environment variables
export ETHEREUM_RPC_URL="https://mainnet.infura.io/v3/YOUR_PROJECT_ID"
export PRIVATE_KEY="your_production_private_key"
export SERVER_HOST="0.0.0.0"
export SERVER_PORT="8080"
export ENCLAVE_ATTESTATION_ENABLED="true"

# Run the application
python enclave/src/main.py
```

### Docker Environment

```bash
# Run Docker with environment variables
docker run -d \
  -p 8080:8080 \
  -e ETHEREUM_RPC_URL="http://host.docker.internal:8545" \
  -e PRIVATE_KEY="your_private_key" \
  enclave-lottery-app
```

## Security Considerations

### Private Key Security

Important notes:

- Never commit real private keys to a Git repository.
- Use secret management services (AWS Secrets Manager, HashiCorp Vault) in production.
- Use test keys for development.

```bash
# Good practice: fetch private key from a secret manager
export PRIVATE_KEY="$(aws secretsmanager get-secret-value --secret-id prod/lottery/private-key --query SecretString --output text)"

# Bad practice: hard-coding a private key in files
PRIVATE_KEY="0x1234567890abcdef..."  # Dangerous!
```

### Network Security

- Use trusted RPC providers (Infura, Alchemy).
- Enable TLS in production.
- Restrict server bind address.

### File Permissions

```bash
# Set secure file permissions
chmod 600 .env
chmod 644 enclave/config/enclave.conf
```

## Configuration Validation

The project validates configuration on startup:

```python
# Required configuration entries
required_configs = [
    'blockchain.rpc_url',
    'blockchain.chain_id',
    'server.host',
    'server.port'
]

# Validate numeric ranges
assert config['lottery']['draw_interval_minutes'] >= 1
assert config['server']['port'] > 0 and config['server']['port'] < 65536
```

## Troubleshooting

### Configuration load failures

```bash
# Check file permissions
ls -la .env

# Check .env format
cat .env | grep -v '^#' | grep '='

# Validate JSON format
python -m json.tool enclave/config/enclave.conf
```

### Environment variables not applied

```bash
# Check environment variables
printenv | grep -E "(ETHEREUM|LOTTERY|ENCLAVE)_"

# Check variable spelling
echo $ETHEREUM_RPC_URL
```

### Private key issues

```bash
# Validate private key format (should start with 0x and have 64 hex chars)
echo $PRIVATE_KEY | grep -E '^0x[a-fA-F0-9]{64}$'
```

## Migration Guide

Migrate from legacy variable names to the new standard names:

```bash
# Legacy → New
BLOCKCHAIN_RPC_URL → ETHEREUM_RPC_URL
BLOCKCHAIN_CHAIN_ID → CHAIN_ID
BLOCKCHAIN_CONTRACT_ADDRESS → CONTRACT_ADDRESS
BLOCKCHAIN_PRIVATE_KEY → PRIVATE_KEY
LOTTERY_SERVER_HOST → SERVER_HOST
LOTTERY_SERVER_PORT → SERVER_PORT
```

Note: Legacy variable names are still supported for backward compatibility, but migration to the new standard names is recommended.

## Example Configurations

### Local Development

```bash
# .env file
ETHEREUM_RPC_URL=http://localhost:8545
CHAIN_ID=31337
PRIVATE_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
SERVER_HOST=localhost
SERVER_PORT=8080
LOTTERY_DRAW_INTERVAL_MINUTES=5
```

### Testnet

```bash
# .env file
ETHEREUM_RPC_URL=https://goerli.infura.io/v3/YOUR_PROJECT_ID
CHAIN_ID=5
PRIVATE_KEY=your_testnet_private_key
CONTRACT_ADDRESS=0x1234567890123456789012345678901234567890
LOTTERY_DRAW_INTERVAL_MINUTES=10
```

### Mainnet

```bash
# Environment variables (do not store these in a file)
export ETHEREUM_RPC_URL="https://mainnet.infura.io/v3/YOUR_PROJECT_ID"
export CHAIN_ID="1"
export PRIVATE_KEY="$(aws secretsmanager get-secret-value ...)"
export CONTRACT_ADDRESS="your_deployed_contract_address"
export ENCLAVE_ATTESTATION_ENABLED="true"
export LOTTERY_DRAW_INTERVAL_MINUTES="60"
```

## More Information

- [Deployment guide](deployment.md)
- [Security guide](security.md)
- [Development guide](DEVELOPMENT.md)
- [Main README](../README.md)