#!/bin/bash
# Deploy Lottery Contract using Forge
# Usage: ./deploy_contract.sh [PUBLISHER_COMMISSION_RATE] [RPC_URL]

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "=========================================="
echo "  Lottery Contract Deployment (Forge)"
echo "=========================================="
echo ""

# Configuration
RPC_URL=${2:-"https://base-sepolia.drpc.org"}
PUBLISHER_PRIVATE_KEY=${PUBLISHER_PRIVATE_KEY:-""}
ETHERSCAN_API_KEY=${ETHERSCAN_API_KEY:-""}

# Contract path
CONTRACT_PATH="contracts/Lottery.sol:Lottery"

# Check if forge is available
if ! command -v forge &> /dev/null; then
    echo -e "${RED}❌ Error: 'forge' command not found${NC}"
    echo "Please install Foundry: curl -L https://foundry.paradigm.xyz | bash"
    exit 1
fi

# Check for private key
if [ -z "$PUBLISHER_PRIVATE_KEY" ]; then
    echo -e "${RED}❌ Error: PUBLISHER_PRIVATE_KEY environment variable not set${NC}"
    echo ""
    echo "Please set your private key:"
    echo "  export PUBLISHER_PRIVATE_KEY=0x..."
    echo ""
    echo "Or use --interactive mode (see below)"
    exit 1
fi

# check for etherscan api key here, if not set, exit 1
if [ -z "$ETHERSCAN_API_KEY" ]; then
    echo -e "${RED}❌ Error: ETHERSCAN_API_KEY environment variable not set${NC}"
    echo ""
    echo "Please set your Etherscan API key to enable contract verification:"
    echo "  export ETHERSCAN_API_KEY=your_api_key"
    exit 1
fi

# Get publisher commission rate (from argument or user input)
if [ -n "$1" ]; then
    PUBLISHER_COMMISSION_RATE=$1
else
    echo -e "${BLUE}📊 Publisher Commission Configuration${NC}"
    echo ""
    echo "The publisher (you) will receive a commission from each lottery round."
    echo "This commission is deducted from the total pot before the winner prize."
    echo ""
    echo "Commission Rate Guide:"
    echo "  • 100 = 1%   (e.g., 1 ETH from 100 ETH pot)"
    echo "  • 200 = 2%   (e.g., 2 ETH from 100 ETH pot) ⭐ recommended"
    echo "  • 500 = 5%   (e.g., 5 ETH from 100 ETH pot)"
    echo "  • 1000 = 10% (e.g., 10 ETH from 100 ETH pot) - maximum"
    echo ""
    echo "Note: Lower commission = larger winner prizes = more attractive to players"
    echo ""
    read -p "Enter publisher commission rate in basis points (press Enter for 200): " PUBLISHER_COMMISSION_RATE
    PUBLISHER_COMMISSION_RATE=${PUBLISHER_COMMISSION_RATE:-200}
    echo ""
fi

# Validate publisher commission rate
if ! [[ "$PUBLISHER_COMMISSION_RATE" =~ ^[0-9]+$ ]]; then
    echo -e "${RED}❌ Error: PUBLISHER_COMMISSION_RATE must be a number${NC}"
    echo "  Provided: '$PUBLISHER_COMMISSION_RATE'"
    exit 1
fi

if [ "$PUBLISHER_COMMISSION_RATE" -lt 0 ] || [ "$PUBLISHER_COMMISSION_RATE" -gt 1000 ]; then
    echo -e "${RED}❌ Error: PUBLISHER_COMMISSION_RATE must be between 0 and 1000 (0-10%)${NC}"
    echo "  Provided: $PUBLISHER_COMMISSION_RATE basis points"
    exit 1
fi

# Show validated commission rate
COMMISSION_PERCENTAGE=$(echo "scale=2; $PUBLISHER_COMMISSION_RATE / 100" | bc)
echo -e "${GREEN}✅ Commission rate set: $PUBLISHER_COMMISSION_RATE basis points ($COMMISSION_PERCENTAGE%)${NC}"
echo ""

# Check RPC URL
if [ -z "$RPC_URL" ]; then
    echo -e "${RED}❌ Error: RPC_URL is required${NC}"
    exit 1
fi

echo -e "${GREEN}📋 Deployment Configuration:${NC}"
echo "  Contract: $CONTRACT_PATH"
echo "  RPC URL: $RPC_URL"
echo "  Publisher Commission: $PUBLISHER_COMMISSION_RATE basis points ($COMMISSION_PERCENTAGE%)"
echo "  Max Allowed: 1000 basis points (10%)"
echo ""

# Test RPC connection
echo -e "${YELLOW}🔍 Testing RPC connection...${NC}"
CHAIN_ID=$(cast chain-id --rpc-url "$RPC_URL" 2>/dev/null || echo "")
if [ -z "$CHAIN_ID" ]; then
    echo -e "${RED}❌ Error: Cannot connect to RPC URL: $RPC_URL${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Connected to chain ID: $CHAIN_ID${NC}"

# Get deployer address
DEPLOYER_ADDRESS=$(cast wallet address --private-key "$PUBLISHER_PRIVATE_KEY" 2>/dev/null || echo "")
if [ -z "$DEPLOYER_ADDRESS" ]; then
    echo -e "${RED}❌ Error: Invalid private key${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Deployer address: $DEPLOYER_ADDRESS${NC}"

# Check deployer balance
BALANCE=$(cast balance "$DEPLOYER_ADDRESS" --rpc-url "$RPC_URL" 2>/dev/null || echo "0")
BALANCE_ETH=$(cast --to-unit "$BALANCE" ether 2>/dev/null || echo "0")
echo "  Balance: $BALANCE_ETH ETH"

if [ "$BALANCE" == "0" ]; then
    echo -e "${RED}⚠️  Warning: Deployer has 0 balance${NC}"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi
echo ""

# Etherscan verification setup
VERIFY_ARGS=""
if [ -n "$ETHERSCAN_API_KEY" ]; then
    echo -e "${GREEN}✅ Etherscan API key found - verification will be enabled${NC}"
    VERIFY_ARGS="--verify --etherscan-api-key $ETHERSCAN_API_KEY"
else
    echo -e "${YELLOW}⚠️  ETHERSCAN_API_KEY not set - contract will not be verified${NC}"
    echo "  To enable verification, set: export ETHERSCAN_API_KEY=your_api_key"
fi
echo ""

# Confirmation
echo -e "${YELLOW}⚠️  Ready to deploy contract${NC}"
echo "  This will:"
echo "    1. Compile the Lottery contract"
echo "    2. Deploy to: $RPC_URL (Chain ID: $CHAIN_ID)"
echo "    3. Set publisher commission to: $PUBLISHER_COMMISSION_RATE basis points"
if [ -n "$ETHERSCAN_API_KEY" ]; then
    echo "    4. Verify contract on block explorer"
fi
echo ""
read -p "Continue with deployment? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}❌ Deployment cancelled${NC}"
    exit 0
fi

# Deploy contract
echo ""
echo -e "${GREEN}🚀 Deploying contract...${NC}"
echo "========================================"

DEPLOY_OUTPUT=$(forge create "$CONTRACT_PATH" \
    --rpc-url "$RPC_URL" \
    --private-key "$PUBLISHER_PRIVATE_KEY" \
    --broadcast \
    --constructor-args "$PUBLISHER_COMMISSION_RATE" \
    $VERIFY_ARGS 2>&1)

DEPLOY_EXIT_CODE=$?

echo "$DEPLOY_OUTPUT"
echo "========================================"

# Check deployment result
if [ $DEPLOY_EXIT_CODE -ne 0 ]; then
    echo ""
    echo -e "${RED}❌ Deployment failed${NC}"
    exit 1
fi

# Extract contract address
CONTRACT_ADDRESS=$(echo "$DEPLOY_OUTPUT" | grep -i "Deployed to:" | awk '{print $NF}' | tr -d '\n\r')

if [ -z "$CONTRACT_ADDRESS" ]; then
    echo ""
    echo -e "${YELLOW}⚠️  Warning: Could not extract contract address from output${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ Deployment successful!${NC}"
echo ""
echo "=========================================="
echo "  Deployment Summary"
echo "=========================================="
echo "  Contract Address: $CONTRACT_ADDRESS"
echo "  Publisher (You): $DEPLOYER_ADDRESS"
echo "  Commission Rate: $PUBLISHER_COMMISSION_RATE basis points ($(echo "scale=2; $PUBLISHER_COMMISSION_RATE / 100" | bc)%)"
echo "  Chain ID: $CHAIN_ID"
echo "  RPC URL: $RPC_URL"
echo "=========================================="
echo ""

# Save deployment info
TIMESTAMP=$(date +%s)
DEPLOYMENT_FILE="deployments/forge_deployment_${TIMESTAMP}.json"
mkdir -p deployments

cat > "$DEPLOYMENT_FILE" <<EOF
{
  "contract_address": "$CONTRACT_ADDRESS",
  "publisher_address": "$DEPLOYER_ADDRESS",
  "publisher_commission_rate": $PUBLISHER_COMMISSION_RATE,
  "chain_id": $CHAIN_ID,
  "rpc_url": "$RPC_URL",
  "timestamp": $TIMESTAMP,
  "deployed_at": "$(date -u +"%Y-%m-%d %H:%M:%S UTC")",
  "architecture": "2-role",
  "verified": $([ -n "$ETHERSCAN_API_KEY" ] && echo "true" || echo "false")
}
EOF

echo -e "${GREEN}💾 Deployment info saved to: $DEPLOYMENT_FILE${NC}"
echo ""

# Next steps
echo "=========================================="
echo "  📝 Next Steps"
echo "=========================================="
echo ""
echo "1. Set the operator address:"
echo "   ./set_operator.sh $CONTRACT_ADDRESS"
echo ""
echo "=========================================="
echo -e "${GREEN}✨ Done!${NC}"
echo "=========================================="
