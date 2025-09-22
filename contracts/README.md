# Smart Contracts

This directory contains the smart contracts for the Enclave Lottery App.

## Files

- **`Lottery.sol`** - Main lottery contract with role-based architecture
- **`build/`** - Compiled contract artifacts (auto-generated)

## Contract Architecture

The lottery contract implements a role-based system:

- **Admin**: Deploys contracts and sets configuration
- **Operator**: Manages lottery rounds (start/draw)  
- **Players**: Place bets and participate in draws

## Usage

Contracts are compiled and deployed using the admin management tool:

```bash
# Compile and deploy new contract
python3 admin/manage_lottery_contract.py --deploy

# Query existing contracts
python3 admin/manage_lottery_contract.py --query
```

## Development

### Manual Compilation

The management tool automatically compiles contracts, but for manual compilation:

```bash
# Install solc compiler
pip3 install py-solc-x

# Compile manually in Python
import solcx
solcx.install_solc('0.8.19')
solcx.set_solc_version('0.8.19')
compiled = solcx.compile_files(['contracts/Lottery.sol'])
```

### Contract Verification

After deployment, contracts can be verified using:

- Block explorers (Etherscan, etc.)
- Admin management tool query function
- Direct blockchain calls to contract methods

## Security

- Contracts use immutable configuration for security
- Role-based access control prevents unauthorized operations
- Cryptographically secure random number generation
- All funds are handled transparently on-chain