#!/bin/bash
# Set Operator for Lottery Contract (2-Role Architecture)
# Usage: ./set_operator.sh [CONTRACT_ADDRESS] [RPC_URL]

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "=========================================="
echo "  Lottery Contract - Set Operator"
echo "=========================================="
echo ""

# Get parameters
CONTRACT_ADDRESS=${1:-""}
RPC_URL=${2:-"https://base-sepolia.drpc.org"}
PUBLISHER_PRIVATE_KEY=${PUBLISHER_PRIVATE_KEY:-""}

# Check if cast is available
if ! command -v cast &> /dev/null; then
    echo -e "${RED}❌ Error: 'cast' command not found${NC}"
    echo "Please install Foundry: curl -L https://foundry.paradigm.xyz | bash"
    exit 1
fi

# Check for private key
if [ -z "$PUBLISHER_PRIVATE_KEY" ]; then
    echo -e "${RED}❌ Error: PUBLISHER_PRIVATE_KEY environment variable not set${NC}"
    echo ""
    echo "Please set your publisher's private key:"
    echo "  export PUBLISHER_PRIVATE_KEY=0x..."
    echo ""
    echo "Note: Only the publisher can set the operator address."
    exit 1
fi


# Validate contract address
if [ -z "$CONTRACT_ADDRESS" ]; then
    echo -e "${BLUE}� Lottery Contract Address${NC}"
    echo ""
    echo "Enter the deployed lottery contract address where you want to set the operator."
    echo "This should be the address from your deployment output."
    echo ""
    read -p "Contract Address: " CONTRACT_ADDRESS
    echo ""
fi

if [ -z "$CONTRACT_ADDRESS" ]; then
    echo -e "${RED}❌ Error: CONTRACT_ADDRESS is required${NC}"
    exit 1
fi

# Validate contract address format
if [[ ! "$CONTRACT_ADDRESS" =~ ^0x[0-9a-fA-F]{40}$ ]]; then
    echo -e "${RED}❌ Error: Invalid contract address format${NC}"
    echo "Expected: 0x followed by 40 hexadecimal characters"
    echo "Example: 0x5FbDB2315678afecb367f032d93F642f64180aa3"
    exit 1
fi


echo -e "${GREEN}📋 Configuration:${NC}"
echo "  Contract Address: $CONTRACT_ADDRESS"
echo "  RPC URL: $RPC_URL"
echo ""

# Get current contract state
echo -e "${YELLOW}🔍 Checking current contract state...${NC}"

# Test RPC connection
CHAIN_ID=$(cast chain-id --rpc-url "$RPC_URL" 2>/dev/null || echo "")
if [ -z "$CHAIN_ID" ]; then
    echo -e "${RED}❌ Error: Cannot connect to RPC URL: $RPC_URL${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Connected to chain ID: $CHAIN_ID${NC}"

# Get publisher address
PUBLISHER=$(cast call $CONTRACT_ADDRESS "PUBLISHER()(address)" --rpc-url $RPC_URL 2>/dev/null || echo "")
if [ -z "$PUBLISHER" ]; then
    echo -e "${RED}❌ Error: Cannot read contract. Check CONTRACT_ADDRESS${NC}"
    exit 1
fi
echo "  Publisher: $PUBLISHER"

# Verify the caller is the publisher
CALLER_ADDRESS=$(cast wallet address --private-key "$PUBLISHER_PRIVATE_KEY" 2>/dev/null || echo "")
if [ -z "$CALLER_ADDRESS" ]; then
    echo -e "${RED}❌ Error: Invalid private key${NC}"
    exit 1
fi
echo "  Your Address: $CALLER_ADDRESS"

if [ "${CALLER_ADDRESS,,}" != "${PUBLISHER,,}" ]; then
    echo -e "${RED}❌ Error: You are not the publisher of this contract${NC}"
    echo "  Publisher: $PUBLISHER"
    echo "  Your Address: $CALLER_ADDRESS"
    echo ""
    echo "Only the publisher can set the operator."
    exit 1
fi
echo -e "${GREEN}✅ You are the publisher${NC}"

# Get current operator
CURRENT_OPERATOR=$(cast call $CONTRACT_ADDRESS "operator()(address)" --rpc-url $RPC_URL 2>/dev/null || echo "0x0000000000000000000000000000000000000000")
echo "  Current Operator: $CURRENT_OPERATOR"

# Get round state
ROUND_DATA=$(cast call $CONTRACT_ADDRESS "round()(uint256,uint256,uint256,uint256,uint256,uint256,uint256,address,uint256,uint256,uint8)" --rpc-url $RPC_URL 2>/dev/null || echo "")
if [ -n "$ROUND_DATA" ]; then
    ROUND_STATE=$(echo "$ROUND_DATA" | tail -n 1)
    case $ROUND_STATE in
        0) STATE_NAME="WAITING" ;;
        1) STATE_NAME="BETTING" ;;
        2) STATE_NAME="DRAWING" ;;
        3) STATE_NAME="COMPLETED" ;;
        4) STATE_NAME="REFUNDED" ;;
        *) STATE_NAME="UNKNOWN" ;;
    esac
    echo "  Round State: $STATE_NAME ($ROUND_STATE)"
    
    if [ "$ROUND_STATE" != "0" ]; then
        echo -e "${YELLOW}⚠️  Warning: Round is not in WAITING state${NC}"
        echo "  Setting operator is only allowed when round state is WAITING"
        echo "  Current state: $STATE_NAME"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
fi
echo ""

# Get operator address from user
echo -e "${BLUE}👤 Operator Address Configuration${NC}"
echo ""
echo "The operator will be responsible for:"
echo "  • Initializing lottery rounds"
echo "  • Drawing winners after betting period"
echo "  • Managing round lifecycle"
echo ""
echo "Current operator: $CURRENT_OPERATOR"
echo ""
read -p "Enter new operator address: " OPERATOR_ADDRESS
echo ""

if [ -z "$OPERATOR_ADDRESS" ]; then
    echo -e "${RED}❌ Error: Operator address is required${NC}"
    exit 1
fi

# Validate operator address format
if [[ ! "$OPERATOR_ADDRESS" =~ ^0x[0-9a-fA-F]{40}$ ]]; then
    echo -e "${RED}❌ Error: Invalid operator address format${NC}"
    echo "Expected: 0x followed by 40 hexadecimal characters"
    exit 1
fi

# Validate operator address
if [ "$OPERATOR_ADDRESS" == "0x0000000000000000000000000000000000000000" ]; then
    echo -e "${RED}❌ Error: Invalid operator address (cannot be zero address)${NC}"
    exit 1
fi

if [ "${OPERATOR_ADDRESS,,}" == "${PUBLISHER,,}" ]; then
    echo -e "${RED}❌ Error: Operator cannot be the same as publisher${NC}"
    echo "  Publisher: $PUBLISHER"
    echo "  Operator: $OPERATOR_ADDRESS"
    exit 1
fi

# Show summary and confirm
echo -e "${GREEN}✅ Operator address validated${NC}"
echo ""
echo "=========================================="
echo "  Summary"
echo "=========================================="
echo "  Contract: $CONTRACT_ADDRESS"
echo "  Chain ID: $CHAIN_ID"
echo "  Publisher (You): $CALLER_ADDRESS"
echo "  Current Operator: $CURRENT_OPERATOR"
echo "  New Operator: $OPERATOR_ADDRESS"
echo "=========================================="
echo ""

# Confirm before sending transaction
echo -e "${YELLOW}⚠️  Ready to update operator address${NC}"
read -p "Continue with this transaction? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}❌ Operation cancelled${NC}"
    exit 0
fi

# Send transaction
echo ""
echo -e "${GREEN}📤 Sending transaction...${NC}"
echo "=========================================="

TX_OUTPUT=$(cast send $CONTRACT_ADDRESS \
    "setOperator(address)" \
    $OPERATOR_ADDRESS \
    --rpc-url $RPC_URL \
    --private-key $PUBLISHER_PRIVATE_KEY \
    2>&1)

TX_EXIT_CODE=$?

echo "$TX_OUTPUT"
echo "=========================================="

if [ $TX_EXIT_CODE -ne 0 ]; then
    echo ""
    echo -e "${RED}❌ Transaction failed${NC}"
    exit 1
fi

# Extract transaction hash
TX_HASH=$(echo "$TX_OUTPUT" | grep -i "transactionHash" | awk '{print $NF}' | tr -d '",' || echo "")

if [ -z "$TX_HASH" ]; then
    TX_HASH=$(echo "$TX_OUTPUT" | grep -o '0x[0-9a-fA-F]\{64\}' | head -n 1 || echo "")
fi

echo ""
if [ -n "$TX_HASH" ]; then
    echo -e "${GREEN}✅ Transaction sent!${NC}"
    echo "  TX Hash: $TX_HASH"
else
    echo -e "${YELLOW}⚠️  Transaction may have been sent, but hash could not be extracted${NC}"
fi
echo ""

# Wait for confirmation
echo -e "${YELLOW}⏳ Waiting for confirmation...${NC}"
sleep 3

# Verify the change
echo -e "${YELLOW}🔍 Verifying operator update...${NC}"
NEW_OPERATOR=$(cast call $CONTRACT_ADDRESS "operator()(address)" --rpc-url $RPC_URL 2>/dev/null || echo "")

if [ "${NEW_OPERATOR,,}" == "${OPERATOR_ADDRESS,,}" ]; then
    echo -e "${GREEN}✅ Success! Operator updated successfully${NC}"
    echo "  New Operator: $NEW_OPERATOR"
else
    echo -e "${RED}⚠️  Warning: Operator may not have been updated${NC}"
    echo "  Expected: $OPERATOR_ADDRESS"
    echo "  Current:  $NEW_OPERATOR"
    if [ -n "$TX_HASH" ]; then
        echo "  Please check transaction: $TX_HASH"
    fi
fi

echo ""
echo "=========================================="
echo -e "${GREEN}✨ Done!${NC}"
echo "=========================================="
echo ""
echo "📝 Next Steps:"
echo ""
echo ""
echo "1. Update your enclave configuration with the contract address & operator address"
echo ""
echo "  enclave/lottery.conf"
echo "      operator_address = $OPERATOR_ADDRESS"
echo "      contract_address = $CONTRACT_ADDRESS"
echo ""
