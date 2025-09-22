# Contract Tools (folder summary)

Role-focused CLI tools for deploying and managing the Lottery smart contract. This document summarizes the `contract-tools/` folder based on the current code, not on any prior README content.

## What’s in this folder

- `publisher.py` — Publisher tool: deploy contracts, set sparsity, query your deployments
- `sparsity.py` — Sparsity tool: set/update operator, fund operator, query your deployments
- `common.py` — Shared helpers (Web3 connection, contract compilation, deployment discovery, display)
- `config.py` — Loads `publisher.conf` / `sparsity.conf` with validations and helpful errors
- `publisher.conf.example` — Publisher config template
- `sparsity.conf.example` — Sparsity config template
- `deployments/` — Deployment records (`deployment_*.json`), auto-created

## Prerequisites

- Python 3.8+
- Dependencies: web3, eth-account, py-solc-x (Solidity 0.8.19 is installed/selected by tools)
- A running Ethereum-compatible node (default: `http://localhost:8545`)

Tip: If you see `ModuleNotFoundError: No module named 'solcx'`, install with `pip3 install py-solc-x`.

## Quick start

```bash
cd contract-tools
cp publisher.conf.example publisher.conf   # add your publisher private key
cp sparsity.conf.example sparsity.conf     # add your sparsity private key
```

## Publisher tool (`publisher.py`)

Modes:
- `--deploy` — Deploy a new Lottery contract
- `--query` — List contracts you deployed (with status)
- `--set-sparsity` — One-time call to set the sparsity address for a contract

Key flags:
- `--publisher-commission-rate <bps>` (default 200)
- `--sparsity-commission-rate <bps>` (default 300)
- `--deployment-output <path>` (default from `publisher.conf` → `output.deployment_output`, usually `deployments/`)
- `--contract <address>` (for `--set-sparsity`)
- `--sparsity <address>` (for `--set-sparsity`)

Blockchain flags (provided by common parser):
- `--rpc-url <url>` (default from config)
- `--private-key <hex>` (default from config)
- `--chain-id <id>` (default from config)

Examples:
```bash
# Deploy with defaults from config
./publisher.py --deploy

# Deploy with custom commission rates
./publisher.py --deploy \
  --publisher-commission-rate 250 \
  --sparsity-commission-rate 300

# Set sparsity (one-time)
./publisher.py --set-sparsity --contract 0x123... --sparsity 0xabc...

# Query your deployments
./publisher.py --query
```

## Sparsity tool (`sparsity.py`)

Modes:
- `--set-operator` — Set operator for a contract
- `--update-operator` — Update operator for a contract
- `--fund-operator` — Send ETH to operator address
- `--query` — List contracts where you are sparsity

Key flags:
- `--contract <address>` (for set/update operator)
- `--operator <address>` (target operator)
- `--amount <eth>` (for `--fund-operator`)

Blockchain flags (provided by common parser):
- `--rpc-url <url>` (default from config)
- `--private-key <hex>` (default from config)
- `--chain-id <id>` (default from config)

Examples:
```bash
# Interactive mode (menus)
./sparsity.py

# Set operator
./sparsity.py --set-operator --contract 0x123... --operator 0xdef...

# Fund operator with 2 ETH
./sparsity.py --fund-operator --operator 0xdef... --amount 2

# Query your contracts
./sparsity.py --query
```

## Configuration files

Both tools load their config from files in `contract-tools/`.

Publisher (`publisher.conf`):
```json
{
  "blockchain": {
    "rpc_url": "http://localhost:8545",
    "private_key": "0x...",
    "chain_id": 31337
  },
  "contract": {
    "publisher_commission_rate": 200,
    "sparsity_commission_rate": 300
  },
  "output": {
    "deployment_output": "deployments/"
  }
}
```

Sparsity (`sparsity.conf`):
```json
{
  "blockchain": {
    "rpc_url": "http://localhost:8545",
    "private_key": "0x...",
    "chain_id": 31337
  },
  "funding": {
    "default_operator_funding": 1.0,
    "auto_fund_threshold": 0.1
  }
}
```

Validation & helpful errors:
- Missing file: tools exit with instructions to copy from `*.conf.example`
- Invalid JSON: tools print an error with details and exit

## Deployment records

- Written to `contract-tools/deployments/` as `deployment_*.json`
- Include: contract address, ABI, deployer, tx hash, block, gas used, timestamp
- Auto-discovered by the tools for queries and updates

## Notes & security

- Never commit real private keys; keep `.conf` files out of version control
- Protect deployment records (contract ABIs + addresses)
- Commission rate limits are enforced by the tool (max 5% each, 10% combined)
- Contract compilation uses Solidity 0.8.19 via `py-solc-x`
