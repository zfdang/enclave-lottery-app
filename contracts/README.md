# Smart Contracts

This directory contains the smart contracts for the Enclave Lottery App with 4-role architecture.

## Files

- **`Lottery.sol`** - Main lottery contract with 4-role architecture
- **`build/`** - Compiled contract artifacts (auto-generated)

## Contract Architecture

The lottery contract implements a 4-role system:

- **Publisher**: Deploys contracts, receives commission (2% default), sets sparsity (one-time)
- **Sparsity**: Manages operator nodes in cloud, receives commission (3% default)
- **Operator**: Manages lottery rounds (start/draw), operational role only
- **Players**: Place bets and participate in draws, receive winnings (95% default)

## Role Flow

```
Publisher → Deploys → Sets Sparsity → Steps Back
Sparsity → Manages Operator → Receives Commission  
Operator → Runs Rounds → Conducts Draws
Players → Place Bets → Receive Winnings
```

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