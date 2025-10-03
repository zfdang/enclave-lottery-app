# Configuration (Passive Operator)

Authoritative list of active configuration namespaces & keys used by the current passive event‑driven implementation. Legacy lottery engine variables (draw_interval_minutes, single_bet_amount, scheduler knobs, REACT_APP_*) have been removed.

## Precedence
1. Environment variables (highest)
2. JSON config file (`enclave/config/enclave.conf`)
3. Internal defaults (lowest)

## Configuration File (`enclave/config/enclave.conf`)
Only include keys you wish to override; environment vars can still supersede them.

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 6080
  },
  "event_manager": {
    "poll_interval_seconds": 2,
    "config_refresh_seconds": 15,
    "history_capacity": 50,
    "feed_capacity": 200
  },
  "blockchain": {
    "rpc_url": "http://localhost:8545",
    "chain_id": 31337,
    "contract_address": "0x...",
    "operator_private_key": "0xTESTKEY...",
    "gas_price": null,
    "gas_multiplier": 1.15
  },
  "enclave": {
    "vsock_port": 5005,
    "attestation_enabled": false
  }
}
```

## Environment Variables

Prefer exporting only what you need for the deployment surface rather than a large `.env` checked into images.

### Namespaces (Prefixes)

| Prefix | Purpose | Examples |
|--------|---------|----------|
| `BLOCKCHAIN_` | On‑chain connectivity & tx signing | `BLOCKCHAIN_RPC_URL`, `BLOCKCHAIN_CHAIN_ID`, `BLOCKCHAIN_CONTRACT_ADDRESS`, `BLOCKCHAIN_OPERATOR_PRIVATE_KEY`, `BLOCKCHAIN_GAS_PRICE`, `BLOCKCHAIN_GAS_MULTIPLIER` |
| `EVENTMGR_` | Polling & retention behavior | `EVENTMGR_POLL_INTERVAL_SECONDS`, `EVENTMGR_CONFIG_REFRESH_SECONDS`, `EVENTMGR_HISTORY_CAPACITY`, `EVENTMGR_FEED_CAPACITY` |
| `SERVER_` | API binding | `SERVER_HOST`, `SERVER_PORT` |
| `APP_` | Logging & app-level | `APP_LOG_LEVEL`, `APP_LOG_FILE` |
| `ENCLAVE_` | Nitro specifics (optional) | `ENCLAVE_VSOCK_PORT`, `ENCLAVE_ATTESTATION_ENABLED` |
| `VITE_` | Frontend build/runtime | `VITE_API_URL`, `VITE_WS_URL`, `VITE_CHAIN_ID` |

### Active Keys (Summary)

| Variable | Description | Default (if unset) |
|----------|-------------|--------------------|
| `BLOCKCHAIN_RPC_URL` | Ethereum RPC endpoint | `http://127.0.0.1:8545` |
| `BLOCKCHAIN_CHAIN_ID` | Chain ID (int) | `31337` |
| `BLOCKCHAIN_CONTRACT_ADDRESS` | Deployed Lottery.sol address | none (required for operations) |
| `BLOCKCHAIN_OPERATOR_PRIVATE_KEY` | Operator EOA private key (hex) | none (draw/refund disabled if absent) |
| `BLOCKCHAIN_GAS_PRICE` | Override gas price (gwei) | auto from node |
| `BLOCKCHAIN_GAS_MULTIPLIER` | Multiply gas estimate | `1.15` |
| `EVENTMGR_POLL_INTERVAL_SECONDS` | Base poll interval (round + participants) | `2` |
| `EVENTMGR_CONFIG_REFRESH_SECONDS` | Contract config refresh interval | `15` |
| `EVENTMGR_HISTORY_CAPACITY` | Retained completed/refunded rounds | `50` |
| `EVENTMGR_FEED_CAPACITY` | Activity feed entries | `200` |
| `SERVER_HOST` | Bind host | `0.0.0.0` |
| `SERVER_PORT` | Bind port | `6080` |
| `APP_LOG_LEVEL` | Logging level | `INFO` |
| `APP_LOG_FILE` | Optional log file path | unset (stdout only) |
| `ENCLAVE_VSOCK_PORT` | Vsock port (enclave mode) | `5005` |
| `ENCLAVE_ATTESTATION_ENABLED` | Enable attestation features | `false` |
| `VITE_API_URL` | Frontend API base | `http://localhost:6080` (dev) |
| `VITE_WS_URL` | Frontend websocket URL | `ws://localhost:6080/ws` (dev) |

Deprecated / removed: all `LOTTERY_*` timing & betting amount vars, `REACT_APP_*` vars, legacy `PRIVATE_KEY` / `ETHEREUM_RPC_URL` alias names.

## Usage Examples

### Development (shell exports)

```bash
# 1. Copy the template
cp .env.example .env

# 2. Edit configuration
nano .env

# 3. Export required environment variables (optional)
export BLOCKCHAIN_RPC_URL=http://localhost:8545
export BLOCKCHAIN_CHAIN_ID=31337
export BLOCKCHAIN_OPERATOR_PRIVATE_KEY=0xYOURKEY
export BLOCKCHAIN_CONTRACT_ADDRESS=0xDEPLOYED

# 4. Run the application
python enclave/src/main.py
```

### Production (minimal set)

Use environment variables in production instead of a `.env` file:

```bash
# Set environment variables
export BLOCKCHAIN_RPC_URL="https://rpc.your-network.example"
export BLOCKCHAIN_CHAIN_ID=12345
export BLOCKCHAIN_CONTRACT_ADDRESS=0x...
export BLOCKCHAIN_OPERATOR_PRIVATE_KEY=$(aws secretsmanager get-secret-value --secret-id prod/lottery/operator-key --query SecretString --output text)
export APP_LOG_LEVEL=INFO

# Run the application
python enclave/src/main.py
```

### Docker Run

```bash
# Run Docker with environment variables
docker run -d \
  -p 6080:6080 \
  -e BLOCKCHAIN_RPC_URL=http://host.docker.internal:8545 \
  -e BLOCKCHAIN_OPERATOR_PRIVATE_KEY=0xYOURKEY \
  enclave-lottery-app
```

## Security Considerations

### Private Key Handling

Important notes:

- Never commit real private keys to a Git repository.
- Use secret management services (AWS Secrets Manager, HashiCorp Vault) in production.
- Use test keys for development.

```bash
# Good practice: fetch private key from a secret manager
export BLOCKCHAIN_OPERATOR_PRIVATE_KEY="$(aws secretsmanager get-secret-value --secret-id prod/lottery/operator-key --query SecretString --output text)"

# Bad practice: hard-coding a private key in files
PRIVATE_KEY="0x1234567890abcdef..."  # Dangerous!
```

### Network

- Use trusted RPC providers (Infura, Alchemy).
- Enable TLS in production.
- Restrict server bind address.

### File Permissions

```bash
# Set secure file permissions
chmod 600 .env
chmod 644 enclave/config/enclave.conf
```

## Validation (Illustrative)

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
assert 0 < config['server']['port'] < 65536
assert 'rpc_url' in config['blockchain']
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
printenv | grep -E "(BLOCKCHAIN_|EVENTMGR_|SERVER_|APP_|ENCLAVE_)"

# Check variable spelling
echo $ETHEREUM_RPC_URL
```

### Private key issues

```bash
# Validate private key format (should start with 0x and have 64 hex chars)
echo $BLOCKCHAIN_OPERATOR_PRIVATE_KEY | grep -E '^0x[a-fA-F0-9]{64}$'
```

## Legacy
Legacy variable names and lottery engine timing variables are no longer recognized. Update deployment manifests accordingly.

## Example Configurations

### Local Development

```bash
# .env file
BLOCKCHAIN_RPC_URL=http://localhost:8545
BLOCKCHAIN_CHAIN_ID=31337
BLOCKCHAIN_OPERATOR_PRIVATE_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
BLOCKCHAIN_CONTRACT_ADDRESS=0x5FbDB2315678afecb367f032d93F642f64180aa3
SERVER_HOST=0.0.0.0
SERVER_PORT=6080
```

### Testnet

```bash
# .env file
BLOCKCHAIN_RPC_URL=https://sepolia.infura.io/v3/YOUR_PROJECT_ID
BLOCKCHAIN_CHAIN_ID=11155111
BLOCKCHAIN_OPERATOR_PRIVATE_KEY=0xTESTNETKEY...
BLOCKCHAIN_CONTRACT_ADDRESS=0x1234567890123456789012345678901234567890
```

### Mainnet

```bash
# Environment variables (do not store these in a file)
export BLOCKCHAIN_RPC_URL="https://mainnet.infura.io/v3/YOUR_PROJECT_ID"
export BLOCKCHAIN_CHAIN_ID=1
export BLOCKCHAIN_OPERATOR_PRIVATE_KEY="$(aws secretsmanager get-secret-value ...)"
export BLOCKCHAIN_CONTRACT_ADDRESS="0xYourDeployed" 
export ENCLAVE_ATTESTATION_ENABLED=true
```

## More Information

- [Deployment guide](deployment.md)
- [Security guide](security.md)
- [Development guide](development.md)
- [Main README](../README.md)
- (upcoming) `API.md`, `EVENTS.md`