# Contract tools — Lottery contract management

This `contract-tools/` folder contains role-specific command-line tools and helpers for managing the Lottery smart contract in a 4-role architecture.
Purpose
- Provide focused tools for the Publisher and Sparsity roles.
- Avoid a single monolithic admin utility; reduce blast radius for credentials and operations.
Important: role-specific configuration files

Each tool requires a role-specific JSON configuration file located in `contract-tools/`:
- `publisher.conf` (based on `publisher.conf.example`)
- `sparsity.conf` (based on `sparsity.conf.example`)

Quick setup

```bash
cd contract-tools
cp publisher.conf.example publisher.conf   # edit and add your publisher private key
cp sparsity.conf.example sparsity.conf     # edit and add your sparsity private key
```
Quick commands

- Deploy a contract (publisher):

```bash
./publisher.py --deploy
```
- Query contracts (publisher):

```bash
./publisher.py --query
```
- Set sparsity address (publisher, one-time):

```bash
./publisher.py --set-sparsity --contract 0x... --sparsity 0x...
```
- Set/update operator (sparsity):

```bash
./sparsity.py --set-operator --contract 0x... --operator 0x...
```
- Fund operator (sparsity):

```bash
./sparsity.py --fund-operator --operator 0x... --amount 1.5
```
Deployment records

- Deployment metadata (ABI, address, deployer, tx hash and block) are stored in `contract-tools/deployments/` as `deployment_*.json` files. Keep these safe — they include ABIs and addresses used by the admin tools.

Troubleshooting

- If a tool exits immediately with a message like `Publisher configuration file not found: contract-tools/publisher.conf`, run:

	```bash
	cd contract-tools
	cp publisher.conf.example publisher.conf
	# then edit publisher.conf and re-run the tool
	```
- If you see `Invalid JSON in ...`, open the file and fix the JSON syntax.

- If deployment fails with `Incorrect argument count` during deployment, ensure the local `contracts/Lottery.sol` constructor signature matches the tooling (current tools expect the 2-arg constructor above).

Security notes

- Do not commit real private keys into git. Add role-specific `.conf` files to `.gitignore`.
- Protect deployment records — they list contract addresses and ABIs.

Further reading

- `publisher.conf.example` and `sparsity.conf.example` show the expected JSON structure for each role.
- `CONFIGURATION.md` contains expanded configuration guidance.


# Lottery Contract Management Tools

Administrative tools for managing lottery smart contracts with a 4-role architecture. The system is refactored into specialized, role-based tools for better security, usability, and maintainability.

## Architecture Overview

The lottery system uses a 4-role architecture with dedicated management tools:

- **Publisher**: Deploys contracts and receives commission (2% default) → Uses `publisher.py`
- **Sparsity**: Manages operator nodes, receives commission (3% default) → Uses `sparsity.py`
- **Operator**: Manages lottery rounds and draws (operational role only) → Web interface
- **Player**: Places bets and receives winnings → Web interface

### Role Flow

```
Publisher → Deploys Contract → Sets Sparsity → Steps Back
Sparsity → Sets/Updates Operator → Funds Operator → Receives Commission
Operator → Manages Rounds → Conducts Draws
Players → Place Bets → Receive Winnings
```

## Tool Architecture

The management system is split into focused, role-specific tools:

### 🚀 Publisher Tool (`publisher.py`)
**Role**: Contract deployment and one-time sparsity setting

- Deploy new contracts
- Set sparsity address (one-time)
- Query contracts where you are publisher

**Command Line Usage**:
```bash
# Interactive mode (default)
./publisher.py
# Query contracts where you are publisher
./publisher.py --query
# Deploy new contract with custom parameters
./publisher.py --deploy --min-bet 0.005 --betting-duration 1800
# Set sparsity for a specific contract
./publisher.py --set-sparsity --contract 0x123... --sparsity 0xabc...
```

### ⚙️ Sparsity Tool (`sparsity.py`)
**Role**: Operator management and funding operations

- Set/update operator addresses
- Fund operator addresses with ETH
- Query contracts where you are sparsity

**Command Line Usage**:
```bash
# Interactive mode (default)
./sparsity.py
# Query contracts where you are sparsity
./sparsity.py --query
# Set operator for a contract
./sparsity.py --set-operator --contract 0x123... --operator 0xdef...
# Fund operator with ETH
./sparsity.py --fund-operator --operator 0xdef... --amount 1.5
```

### 📚 Shared Utilities (`common.py`)
- `LotteryContractBase`: Base class for all management tools
- Contract compilation and deployment utilities
- Transaction handling and ETH transfer functions
- Address validation and formatting
- File-based deployment tracking
- Common display functions

## Role-Based Security Model

**Publisher Permissions**
- Deploy new contracts
- Set initial sparsity address (one-time only)
- Query contracts where they are publisher
- Configure contract parameters during deployment

**Sparsity Permissions**
- Set/update operator addresses on their contracts
- Fund operator addresses with ETH
- Query contracts where they are sparsity
- Manage multiple operators across contracts

**Operator & Player Roles**
- Managed through the web interface and contract interactions
- No direct management tools (players interact through UI)

## Benefits of This Architecture

1. **Role Separation**: Each tool only exposes relevant functionality
2. **Security**: Role-based access control prevents unauthorized operations
3. **Usability**: Simplified interfaces focused on specific use cases
4. **Maintainability**: Shared utilities reduce code duplication
5. **Extensibility**: Easy to add new role-specific tools
6. **Clarity**: Clear separation of responsibilities

## File Structure

```
contract-tools/
├── common.py                 # Shared utilities and base classes
├── publisher.py              # Publisher tool (executable)
├── sparsity.py               # Sparsity tool (executable)
├── config.py                 # Configuration management
├── publisher.conf.example    # Publisher config template
├── sparsity.conf.example     # Sparsity config template
├── deployments/              # Contract deployment records (auto-created)
│   ├── contract_YYYYMMDD_HHMMSS.json
│   └── ...
├── README.md                 # This documentation
├── CONFIGURATION.md          # Configuration setup guide
├── GIT_TRACKING.md           # Git ignore and security notes
└── TOOLS_ARCHITECTURE.md     # (merged here)
```

## Migration from Legacy Tool

The original `manage_lottery_contract.py` provided all functionality in one tool. The new architecture provides:

- **Better Security**: Role-based access prevents accidental operations
- **Improved UX**: Focused interfaces for specific roles
- **Cleaner Code**: Separated concerns and shared utilities
- **Future-Proof**: Easier to extend with new role-specific features

---

## Quick Start & Usage Examples

### Complete Workflow Example

1. **Publisher deploys contract**:
	```bash
	./publisher.py --deploy --min-bet 0.01
	```
2. **Publisher sets sparsity**:
	```bash
	./publisher.py --set-sparsity --contract 0x123... --sparsity 0xabc...
	```
3. **Sparsity sets operator**:
	```bash
	./sparsity.py --set-operator --contract 0x123... --operator 0xdef...
	```
4. **Sparsity funds operator**:
	```bash
	./sparsity.py --fund-operator --operator 0xdef... --amount 2.0
	```

### Interactive Mode
Both tools default to interactive mode, providing guided menus for all operations.

### Query Contracts by Role
```bash
# Query contracts where you are publisher
./publisher.py --query
# Query contracts where you are sparsity
./sparsity.py --query
```

---

## Configuration

### Role-Specific Configuration

The new architecture uses role-specific configuration files for better organization and security:

**For Publishers** (`publisher.conf`):
```bash
cp publisher.conf.example publisher.conf
# Edit publisher.conf with your publisher private key and settings
```

**For Sparsity Managers** (`sparsity.conf`):
```bash
cp sparsity.conf.example sparsity.conf
# Edit sparsity.conf with your sparsity private key and settings
```

### Configuration Priority

Settings are loaded in this order (later overrides earlier):

1. **Built-in Defaults** - Safe development defaults
2. **Role-specific Config** - `publisher.conf` or `sparsity.conf`
3. **Legacy Config** - `admin.conf` (fallback)
4. **Command Line Arguments** - Override any setting

See `CONFIGURATION.md` for detailed setup instructions and examples.

---

## Error Handling & Security

- Address validation for all Ethereum addresses
- Balance checking before transactions
- Contract state validation
- Clear error messages with suggested solutions
- Graceful handling of network issues

### Security Notes

- **Private Keys**: Never commit real private keys to version control
- **Configuration**: Use role-specific config files (add to `.gitignore`)
- **Deployment Records**: Backup deployment files - they contain contract ABIs and addresses
- **Operator Access**: Only set trusted addresses as contract operators
- **Admin Access**: Admin has full contract control - secure the admin private key

See `GIT_TRACKING.md` for more security and gitignore details.

---

## Future Enhancements

- **Operator Tool**: Management interface for operators
- **Multi-signature Support**: Enhanced security for high-value operations
- **Batch Operations**: Bulk management of multiple contracts
- **Monitoring Dashboard**: Real-time contract status monitoring

## Quick Start

### 1. Deploy a New Contract (Publisher Role)

```bash
# Interactive deployment (recommended)
./publisher.py

# Command line deployment with default configuration
./publisher.py --deploy

# Deploy with custom commission rates and parameters
./publisher.py --deploy --publisher-commission-rate 150 --sparsity-commission-rate 250 --min-bet 0.005
```

### 2. Set Sparsity Address (Publisher Role - One Time Only)

```bash
# Interactive sparsity setting
./publisher.py

# Command line sparsity setting
./publisher.py --set-sparsity --contract 0x123... --sparsity 0xabc...
```

### 3. Set/Update Operator (Sparsity Role)

```bash
# Interactive operator management
./sparsity.py

# Command line operator setting
./sparsity.py --set-operator --contract 0x123... --operator 0xdef...
```

### 4. Fund Operator (Sparsity Role)

```bash
# Interactive funding
./sparsity.py

# Command line funding
./sparsity.py --fund-operator --operator 0xdef... --amount 2.0
```

# Contract tools — Lottery contract management

This `contract-tools/` folder contains role-specific command-line tools and helpers for managing the Lottery smart contract in a 4-role architecture.

Purpose
- Provide focused tools for the Publisher and Sparsity roles.
- Reduce blast radius for credentials and operations by avoiding a single monolithic admin script.

Included utilities
- `publisher.py` — Publisher tool (deploy contracts, set sparsity)
- `sparsity.py` — Sparsity tool (set/update operator, fund operator)
- `common.py` — Shared helpers (compile, deploy, transactions, displays)
- `config.py` — Configuration loader helpers

Important: role-specific configuration files

Each tool requires a role-specific JSON configuration file in this directory:
- `publisher.conf` (copy from `publisher.conf.example`)
- `sparsity.conf` (copy from `sparsity.conf.example`)

The tools will exit cleanly with a short actionable message if the required `.conf` file is missing or invalid. This is intentional: the tools do not silently fall back to defaults.

Quick setup

```bash
cd contract-tools
cp publisher.conf.example publisher.conf   # customize with publisher private key
cp sparsity.conf.example sparsity.conf     # customize with sparsity private key
```

Quick commands

```bash
# Deploy a contract (publisher)
./publisher.py --deploy

# Query contracts (publisher)
./publisher.py --query

# Set sparsity address (publisher - one-time)
./publisher.py --set-sparsity --contract 0x... --sparsity 0x...

# Set/update operator (sparsity)
./sparsity.py --set-operator --contract 0x... --operator 0x...

# Fund operator (sparsity)
./sparsity.py --fund-operator --operator 0x... --amount 1.5
```

Deployment records

- Deployment metadata (ABI, address, deployer, tx hash and block) are saved under `contract-tools/deployments/` as `deployment_*.json`.

Contract constructor note

- Current `contracts/Lottery.sol` constructor expects only commission rates:

```
constructor(uint256 _publisherCommissionRate, uint256 _sparsityCommissionRate)
```

Operational parameters (min bet, betting duration, draw delay) are managed at runtime by the operator and are not passed during deployment.

Troubleshooting

- Missing configuration file message:

  ```text
  ❌ Publisher configuration file not found: contract-tools/publisher.conf
  💡 Please create contract-tools/publisher.conf based on publisher.conf.example
  ```

- Invalid JSON message: fix the JSON syntax in the `.conf` file.

- Deployment `Incorrect argument count`: ensure `contracts/Lottery.sol` constructor signature matches the tooling.Security notes

- Do not commit real private keys to git. Add role-specific `.conf` files to `.gitignore`.
- Keep deployment records private — they include ABIs and addresses.

Further reading

- `publisher.conf.example` and `sparsity.conf.example` show the expected JSON structure.
- `CONFIGURATION.md` contains expanded configuration guidance.

### Documentation
- **`README.md`** - This file
- **`TOOLS_ARCHITECTURE.md`** - Detailed architecture documentation
- **`CONFIGURATION.md`** - Configuration setup guide

## Configuration

### Role-Specific Configuration

The new architecture uses role-specific configuration files for better organization and security:

**For Publishers** (`publisher.conf`):
```bash
cp publisher.conf.example publisher.conf
# Edit publisher.conf with your publisher private key and settings
```

**For Sparsity Managers** (`sparsity.conf`):
```bash
cp sparsity.conf.example sparsity.conf  
# Edit sparsity.conf with your sparsity private key and settings
```

### Configuration Priority

Settings are loaded in this order (later overrides earlier):

1. **Built-in Defaults** - Safe development defaults
2. **Role-specific Config** - `publisher.conf` or `sparsity.conf`
3. **Legacy Config** - `admin.conf` (fallback)
4. **Command Line Arguments** - Override any setting

See `CONFIGURATION.md` for detailed setup instructions and examples.

### Command Line Overrides

Override any setting via command line (all flags are available directly on the tools):

```bash
# Use different blockchain
./publisher.py --rpc-url https://mainnet.infura.io/... --chain-id 1 --deploy

# Custom commission rates
./publisher.py --publisher-commission-rate 200 --sparsity-commission-rate 300 --deploy

# Different private key for querying
./publisher.py --private-key 0x... --query
```

## Deployment Process

### Automatic Deployment

New contracts are deployed using configuration defaults without manual input:

1. **Loads Configuration**: Built-in defaults → config file → command line args
2. **Compiles Contract**: Automatically compiles `Lottery.sol`
3. **Deploys Contract**: Uses configured parameters
4. **Verifies Deployment**: Confirms contract configuration
5. **Saves Records**: Creates timestamped deployment file in `contract-tools/deployments/`
6. (Planned) Operator конфig generation: The tools do not currently generate `operator.conf`. The enclave service loads from `enclave/config/enclave.conf`.

### Using Operator Configuration

Operator configuration is managed within the enclave via `enclave/config/enclave.conf`. There is no `operator.conf` generated by these tools at this time.

To start the enclave operator after setting an operator on-chain:

```bash
cd enclave
python3 src/main.py
```

### Deployment Records

All deployments are automatically saved as:
- **Location**: `contract-tools/deployments/deployment_<timestamp>.json`
- **Content**: Contract address, admin address, configuration, ABI, deployment details
- **Usage**: Automatically detected by management tool for queries and operator management

## Contract Management

### Query Contracts

The tools automatically find and display:
- All deployment files in `contract-tools/deployments/` folder
- Legacy deployment files in `contract-tools/` (for compatibility)
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

## Command Reference

### Publisher
```bash
# Interactive mode (default)
./publisher.py
# Query your contracts
./publisher.py --query
# Deploy new contract
./publisher.py --deploy
# Set sparsity for a contract
./publisher.py --set-sparsity --contract 0x... --sparsity 0x...
```

### Sparsity
```bash
# Interactive mode (default)
./sparsity.py
# Query your contracts
./sparsity.py --query
# Set operator
./sparsity.py --set-operator --contract 0x... --operator 0x...
# Fund operator
./sparsity.py --fund-operator --operator 0x... --amount 1.0
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
- Saves deployments to `contract-tools/deployments/` folder
- Interactive operator management

### Production Setup
1. Create `contract-tools/publisher.conf` and `contract-tools/sparsity.conf` with production settings
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
- Check if deployment file exists in `contract-tools/deployments/` folder
- Verify contract address format
- Use `--query` to see all discovered contracts

### Getting Help

```bash
# Publisher help
./publisher.py --help

# Sparsity help
./sparsity.py --help
```

## File Structure

```
contract-tools/
├── common.py                 # Shared utilities and base classes
├── publisher.py              # Publisher tool (executable)
├── sparsity.py               # Sparsity tool (executable)
├── config.py                 # Configuration management
├── publisher.conf.example    # Publisher config template
├── sparsity.conf.example     # Sparsity config template
├── deployments/              # Contract deployment records (auto-created)
│   ├── deployment_*.json
│   └── ...
└── README.md                 # This documentation
```