#!/bin/bash

# Lottery Enclave Build Script
# This script builds the complete lottery application including Docker images and frontend

set -e

echo "🚀 Starting Lottery Enclave Build Process..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}Project root: $PROJECT_ROOT${NC}"

# Function to log messages
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed. Please install Docker first."
    fi
    
    # Check if Node.js is installed
    if ! command -v node &> /dev/null; then
        warning "Node.js is not installed. Frontend build will be skipped."
        SKIP_FRONTEND=true
    else
        log "Node.js version: $(node --version)"
    fi
    
    # Check if Python is available
    if ! command -v python3 &> /dev/null; then
        error "Python 3 is not installed."
    fi
    
    log "Prerequisites check completed ✅"
}

# Build frontend
build_frontend() {
    if [[ "$SKIP_FRONTEND" == "true" ]]; then
        warning "Skipping frontend build - Node.js not available"
        return
    fi
    
    log "Building React frontend..."
    
    cd "$PROJECT_ROOT/enclave/src/frontend"
    
    # Install dependencies
    if [[ ! -d "node_modules" ]]; then
        log "Installing npm dependencies..."
        npm install
    fi
    
    # Build production frontend
    log "Building production frontend..."
    npm run build
    
    log "Frontend build completed ✅"
    cd "$PROJECT_ROOT"
}

# Build Python backend
build_backend() {
    log "Preparing Python backend..."
    
    cd "$PROJECT_ROOT/enclave"
    
    # Remove existing venv if it's corrupted
    if [[ -d "venv" ]] && [[ ! -f "venv/bin/pip" || ! -x "venv/bin/pip" ]]; then
        log "Removing corrupted virtual environment..."
        rm -rf venv
    fi
    
    # Create virtual environment if it doesn't exist
    if [[ ! -d "venv" ]]; then
        log "Creating Python virtual environment..."
        python3 -m venv venv
    fi
    
    # Activate virtual environment and install dependencies
    log "Installing Python dependencies..."
    source venv/bin/activate
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    
    log "Backend preparation completed ✅"
    cd "$PROJECT_ROOT"
}

# Compile smart contracts
compile_contracts() {
    log "Compiling smart contracts..."
    
    # Check if solc is installed
    if ! command -v solc &> /dev/null; then
        warning "Solidity compiler (solc) not found. Installing..."
        
        # Try to install solc via snap if available
        if command -v snap &> /dev/null; then
            sudo snap install solc
        else
            warning "Could not install solc automatically. Please install manually."
            warning "Smart contract compilation will be skipped."
            return
        fi
    fi
    
    # Use the correct contracts directory
    CONTRACTS_DIR="$PROJECT_ROOT/enclave/src/blockchain/contracts"
    BUILD_DIR="$CONTRACTS_DIR/compiled"
    
    if [[ ! -d "$CONTRACTS_DIR" ]]; then
        warning "Contracts directory not found at $CONTRACTS_DIR"
        return
    fi
    
    cd "$CONTRACTS_DIR"
    
    # Create build directory
    mkdir -p "$BUILD_DIR"
    
    # Compile contracts
    for contract in *.sol; do
        if [[ -f "$contract" ]]; then
            log "Compiling $contract..."
            solc --bin --abi --optimize "$contract" -o "$BUILD_DIR" --overwrite
        fi
    done
    
    log "Smart contract compilation completed ✅"
    cd "$PROJECT_ROOT"
}

# Build Docker image
build_docker() {
    log "Building Docker image..."
    
    cd "$PROJECT_ROOT"
    
    # Build the Docker image with the correct context and name
    # Use the enclave directory as build context since Dockerfile expects relative paths
    docker build -t enclave-lottery-app:latest -f enclave/Dockerfile enclave/
    
    # Also tag it with the alternate name for compatibility
    docker tag enclave-lottery-app:latest lottery-enclave:latest
    
    log "Docker image build completed ✅"
    log "Available tags: enclave-lottery-app:latest, lottery-enclave:latest"
}

# Create environment file if it doesn't exist
create_env_file() {
    if [[ ! -f "$PROJECT_ROOT/.env" ]]; then
        log "Creating environment file..."
        
        cat > "$PROJECT_ROOT/.env" << EOF
# Ethereum Configuration
ETHEREUM_RPC_URL=https://mainnet.infura.io/v3/YOUR_INFURA_PROJECT_ID
PRIVATE_KEY=your_private_key_here
CONTRACT_ADDRESS=

# Enclave Configuration
ENCLAVE_PORT=5000
DEBUG=false
LOG_LEVEL=INFO

# Security Configuration
TLS_CERT_PATH=
TLS_KEY_PATH=

# Frontend Configuration
REACT_APP_WS_URL=ws://localhost:8080
REACT_APP_API_URL=http://localhost:8080
EOF
        
        warning "Created .env file. Please update the configuration values before running the application."
    fi
}

# Main build process
main() {
    log "Starting build process..."
    
    # Create necessary directories
    mkdir -p "$PROJECT_ROOT/enclave/src/blockchain/contracts/compiled"
    mkdir -p "$PROJECT_ROOT/logs"
    mkdir -p "$PROJECT_ROOT/data"
    
    # Run build steps
    check_prerequisites
    create_env_file
    build_backend
    build_frontend
    compile_contracts
    build_docker
    
    log "🎉 Build process completed successfully!"
    log ""
    log "Next steps:"
    log "1. Update the .env file with your configuration"
    log "2. Deploy smart contracts: ./scripts/deploy_contracts.sh"
    log "3. Run the application: ./scripts/run_enclave.sh"
    log ""
    log "For production deployment, also run:"
    log "./scripts/build_enclave.sh  # Build EIF file for AWS Nitro Enclave"
}

# Run main function
main "$@"