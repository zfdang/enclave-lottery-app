# Admin Tools

Administrative tools for managing lottery smart contracts. This directory contains everything needed to deploy, configure, and manage lottery contracts in a production environment.

## Overview

The admin tools provide a complete contract management solution with:
- **Smart Contract Deployment**: Deploy new lottery contracts with configuration defaults
- **Contract Management**: Query deployed contracts and their status
- **Operator Management**: Set and update contract operators
- **Configuration Management**: Centralized configuration for all admin operations

## Quick Start

### 1. Deploy a New Contract

```bash
# Deploy with default configuration
python3 admin/manage_lottery_contract.py --deploy

# Deploy with custom settings
python3 admin/manage_lottery_contract.py --commission-rate 300 --min-bet 0.005 --deploy
```

### 2. Query Deployed Contracts

```bash
# View all deployed contracts
python3 admin/manage_lottery_contract.py --query
```

### 3. Set Contract Operator

```bash
# Interactive operator management
python3 admin/manage_lottery_contract.py --set-operator
python3 admin/manage_lottery_contract.py --set-operator --contract 0x123...

# Set operator for specific contract with command line address
python3 admin/manage_lottery_contract.py --set-operator --contract 0x123...  --operator 0xOperatorAddress...
```

### 4. Interactive Mode

```bash
# Launch interactive menu (default)
python3 admin/manage_lottery_contract.py
```

## Files

### Core Files
- **`manage_lottery_contract.py`** - Main management tool for all admin operations
- **`config.py`** - Configuration management system
- **`admin.conf.example`** - Example configuration file

### Configuration Files
- **`admin.conf`** - Custom configuration (create from example)
- **`deployment_*.json`** - Contract deployment records (auto-generated)
- **`operator.conf`** - Operator configuration for enclave service (auto-generated)

### Documentation
- **`README.md`** - This file
- **`CONFIG_EXAMPLES.md`** - Configuration usage examples

## Configuration

### Default Configuration

The system comes with sensible defaults for development:

```json
{
  "blockchain": {
    "rpc_url": "http://localhost:8545",
    "private_key": "0x2a871d0798f97d79848a013d4936a73bf4cc922c825d33c1cf7073dff6d409c6",
    "chain_id": 31337
  },
  "contract": {
    "commission_rate": 500,
    "min_bet": 0.01,
    "betting_duration": 900,
    "draw_delay": 90
  },
  "output": {
    "config_output": "admin/operator.conf",
    "deployment_output": "admin/deployment.json"
  }
}
```

### Custom Configuration

Create `admin/admin.conf` to override defaults:

```bash
cp admin/admin.conf.example admin/admin.conf
# Edit admin.conf with your settings
```

### Command Line Overrides

Override any setting via command line:

```bash
# Use different blockchain
python3 admin/manage_lottery_contract.py --rpc-url https://mainnet.infura.io/... --chain-id 1

# Custom contract parameters
python3 admin/manage_lottery_contract.py --commission-rate 300 --min-bet 0.005 --deploy

# Different private key
python3 admin/manage_lottery_contract.py --private-key 0x... --query
```

## Deployment Process

### Automatic Deployment

New contracts are deployed using configuration defaults without manual input:

1. **Loads Configuration**: Built-in defaults → config file → command line args
2. **Compiles Contract**: Automatically compiles `Lottery.sol`
3. **Deploys Contract**: Uses configured parameters
4. **Verifies Deployment**: Confirms contract configuration
5. **Saves Records**: Creates timestamped deployment file in `admin/`
6. **Generates Config**: Creates operator configuration in `admin/operator.conf`

### Using Operator Configuration

After deployment, copy the operator configuration to the enclave:

```bash
# Copy operator config to enclave directory
cp admin/operator.conf enclave/config/

# Set operator address before starting service
python3 admin/manage_lottery_contract.py --set-operator

# Start operator service
cd enclave && python3 src/main.py
```

### Deployment Records

All deployments are automatically saved as:
- **Location**: `admin/deployment_<timestamp>.json`
- **Content**: Contract address, admin address, configuration, ABI, deployment details
- **Usage**: Automatically detected by management tool for queries and operator management

## Contract Management

### Query Contracts

The management tool automatically finds and displays:
- All deployment files in `admin/` folder (priority)
- Legacy deployment files in project root and subdirectories
- Contract status and configuration
- Current round information
- Admin and operator addresses

### Operator Management

Set operators for deployed contracts:
- **Interactive Mode**: Select from list of deployed contracts
- **Direct Mode**: Specify contract address directly
- **Address Validation**: Basic Ethereum address format checking
- **Transaction Management**: Handles gas, nonce, and confirmation
- **Record Updates**: Automatically updates deployment files

## Configuration Priority

Settings are applied in this order (later overrides earlier):

1. **Built-in Defaults** - Safe development defaults in `config.py`
2. **Configuration File** - Your persistent settings in `admin.conf`
3. **Command Line Arguments** - One-time overrides for specific operations

## Command Reference

### Basic Operations
```bash
# Interactive mode (default)
python3 admin/manage_lottery_contract.py

# Query all contracts
python3 admin/manage_lottery_contract.py --query

# Deploy new contract
python3 admin/manage_lottery_contract.py --deploy

# Set operator interactively
python3 admin/manage_lottery_contract.py --set-operator
```

### Blockchain Configuration
```bash
--rpc-url URL              # Blockchain RPC endpoint
--private-key KEY          # Admin private key
--chain-id ID              # Blockchain chain ID
```

### Contract Configuration
```bash
--commission-rate RATE     # Commission in basis points (500 = 5%)
--min-bet AMOUNT          # Minimum bet in ETH
--betting-duration SEC    # Betting period in seconds
--draw-delay SEC          # Delay before draw in seconds
```

### Output Configuration
```bash
--config-output PATH      # Operator config output path
--deployment-output PATH  # Deployment record output path
```

### Operator Management
```bash
--contract ADDRESS        # Target contract for operator operations
```

## Development vs Production

### Development Setup
- Uses default configuration for local blockchain
- Default private key for testing
- Saves deployments to `admin/` folder
- Interactive operator management

### Production Setup
1. Create `admin/admin.conf` with production settings
2. Use secure private key management
3. Configure production RPC URL and chain ID
4. Use command line overrides for different environments
5. Backup deployment records for disaster recovery

## Security Notes

- **Private Keys**: Never commit real private keys to version control
- **Configuration**: Use `admin.conf` for sensitive settings (add to `.gitignore`)
- **Deployment Records**: Backup deployment files - they contain contract ABIs and addresses
- **Operator Access**: Only set trusted addresses as contract operators
- **Admin Access**: Admin has full contract control - secure the admin private key

## Troubleshooting

### Common Issues

**"ModuleNotFoundError: No module named 'solcx'"**
```bash
pip3 install py-solc-x
```

**"Could not transact with/call contract function"**
- Check if blockchain is running
- Verify contract address is correct
- Ensure sufficient ETH balance for gas

**"Contract not found in deployment files"**
- Check if deployment file exists in `admin/` folder
- Verify contract address format
- Use `--query` to see all discovered contracts

### Getting Help

```bash
# Show all command options
python3 admin/manage_lottery_contract.py --help

# Interactive mode provides guided operations
python3 admin/manage_lottery_contract.py
```

## File Structure

```
admin/
├── manage_lottery_contract.py    # Main management tool
├── config.py                     # Configuration management
├── admin.conf.example           # Configuration template
├── admin.conf                   # Custom configuration (create from example)
├── deployment_*.json            # Contract deployment records (auto-generated)
├── README.md                    # This documentation
└── CONFIG_EXAMPLES.md           # Configuration examples
```