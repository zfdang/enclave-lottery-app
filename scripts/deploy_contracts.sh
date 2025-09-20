#!/bin/bash

# Deploy Smart Contracts Script
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Default configuration
NETWORK="localhost"
RPC_URL="http://localhost:8545"
PRIVATE_KEY=""
CONTRACT_NAME="Lottery"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --network)
            NETWORK="$2"
            shift 2
            ;;
        --rpc-url)
            RPC_URL="$2"
            shift 2
            ;;
        --private-key)
            PRIVATE_KEY="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [--network <network>] [--rpc-url <url>] [--private-key <key>]"
            echo ""
            echo "Options:"
            echo "  --network      Target network (default: localhost)"
            echo "  --rpc-url      RPC endpoint URL (default: http://localhost:8545)"
            echo "  --private-key  Private key for deployment"
            echo "  --help         Show this help message"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Check if solc is installed
check_solc() {
    print_status "Checking Solidity compiler..."
    
    if ! which solc > /dev/null 2>&1; then
        print_error "Solidity compiler (solc) not found"
        print_status "Installing solc..."
        npm install -g solc
    fi
    
    print_status "Solidity compiler version: $(solc --version | head -n1)"
}

# Compile smart contracts
compile_contracts() {
    print_status "Compiling smart contracts..."
    
    cd enclave/src/blockchain/contracts
    
    # Create compiled directory if it doesn't exist
    mkdir -p compiled
    
    # Compile Lottery contract
    solc --bin --abi --optimize --output-dir compiled ${CONTRACT_NAME}.sol
    
    if [ $? -eq 0 ]; then
        print_status "Contracts compiled successfully"
    else
        print_error "Failed to compile contracts"
        exit 1
    fi
    
    cd - > /dev/null
}

# Deploy contracts using Python script
deploy_contracts() {
    print_status "Deploying contracts to ${NETWORK}..."
    
    # Create deployment script
    cat > deploy_contract.py << EOF
#!/usr/bin/env python3
import json
import sys
from web3 import Web3
from eth_account import Account

# Configuration
RPC_URL = "${RPC_URL}"
PRIVATE_KEY = "${PRIVATE_KEY}"

def main():
    # Connect to blockchain
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    
    if not w3.is_connected():
        print(f"Error: Could not connect to {RPC_URL}")
        sys.exit(1)
    
    print(f"Connected to blockchain: {RPC_URL}")
    print(f"Chain ID: {w3.eth.chain_id}")
    
    # Load account
    if not PRIVATE_KEY:
        print("Error: Private key not provided")
        sys.exit(1)
    
    account = Account.from_key(PRIVATE_KEY)
    print(f"Deploying from account: {account.address}")
    
    # Check balance
    balance = w3.eth.get_balance(account.address)
    print(f"Account balance: {w3.from_wei(balance, 'ether')} ETH")
    
    if balance == 0:
        print("Error: Insufficient balance for deployment")
        sys.exit(1)
    
    # Load contract artifacts
    try:
        with open('enclave/src/blockchain/contracts/compiled/Lottery.bin', 'r') as f:
            bytecode = f.read().strip()
        
        with open('enclave/src/blockchain/contracts/compiled/Lottery.abi', 'r') as f:
            abi = json.load(f)
    except FileNotFoundError as e:
        print(f"Error: Contract artifacts not found: {e}")
        sys.exit(1)
    
    # Create contract instance
    contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    
    # Build deployment transaction
    transaction = contract.constructor().build_transaction({
        'from': account.address,
        'nonce': w3.eth.get_transaction_count(account.address),
        'gas': 2000000,
        'gasPrice': w3.to_wei('20', 'gwei'),
    })
    
    # Sign and send transaction
    signed_txn = account.sign_transaction(transaction)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
    
    print(f"Transaction hash: {tx_hash.hex()}")
    print("Waiting for transaction receipt...")
    
    # Wait for transaction receipt
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    
    if receipt.status == 1:
        print(f"Contract deployed successfully!")
        print(f"Contract address: {receipt.contractAddress}")
        print(f"Gas used: {receipt.gasUsed}")
        
        # Save deployment info
        deployment_info = {
            "network": "${NETWORK}",
            "rpc_url": RPC_URL,
            "contract_address": receipt.contractAddress,
            "deployer": account.address,
            "transaction_hash": tx_hash.hex(),
            "gas_used": receipt.gasUsed,
            "chain_id": w3.eth.chain_id
        }
        
        with open('deployment.json', 'w') as f:
            json.dump(deployment_info, f, indent=2)
        
        print("Deployment info saved to deployment.json")
    else:
        print("Error: Contract deployment failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
EOF

    # Run deployment script
    python3 deploy_contract.py
    
    # Clean up
    rm deploy_contract.py
}

# Update enclave configuration with contract address
update_config() {
    if [ -f "deployment.json" ]; then
        CONTRACT_ADDRESS=$(python3 -c "import json; print(json.load(open('deployment.json'))['contract_address'])")
        
        print_status "Updating enclave configuration with contract address: ${CONTRACT_ADDRESS}"
        
        # Update enclave configuration
        python3 -c "
import json
with open('enclave/config/enclave.conf', 'r') as f:
    config = json.load(f)
config['blockchain']['contract_address'] = '${CONTRACT_ADDRESS}'
with open('enclave/config/enclave.conf', 'w') as f:
    json.dump(config, f, indent=2)
"
        
        print_status "Configuration updated successfully"
    fi
}

# Main deployment function
main() {
    print_status "Starting smart contract deployment"
    
    # Validate inputs
    if [ -z "$PRIVATE_KEY" ]; then
        print_error "Private key is required for deployment"
        print_status "Usage: $0 --private-key <your-private-key>"
        exit 1
    fi
    
    check_solc
    compile_contracts
    deploy_contracts
    update_config
    
    print_status "Smart contract deployment completed!"
    
    if [ -f "deployment.json" ]; then
        print_status "Deployment details:"
        cat deployment.json
    fi
}

# Run main function
main