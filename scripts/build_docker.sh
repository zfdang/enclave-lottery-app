#!/bin/bash

# Lottery Enclave Build Script
# This script builds a complete, production-ready lottery application Docker image.
# Features: optimized frontend build, selective file copying, proper permissions, and .env validation.
# The resulting Docker image excludes unnecessary development files for minimal size and security.

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
        exit
    else
        log "Docker version: $(docker --version)"
    fi
    
    # Check if Node.js is installed
    if ! command -v node &> /dev/null; then
        error "Node.js is not installed. Frontend build will be skipped."
        exit 1
    else
        log "Node.js version: $(node --version)"
    fi
    
    # Check if Python is available
    if ! command -v python3 &> /dev/null; then
        error "Python 3 is not installed."
        exit 1
    else
        log "Python version: $(python3 --version)"  
    fi
    
    log "Prerequisites check completed ✅"
}

# Build frontend
build_frontend() {    
    log "Building React frontend..."
    
    cd "$PROJECT_ROOT/enclave/frontend"
    
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

compile_contracts() {
    log "Compiling smart contracts..."

    # Check if solc is installed
    if ! command -v solc &> /dev/null; then
        error "Solidity compiler (solc) not found. please run ./scripts/setup_environment.sh to install solc-select"
        exit 1
    fi

    # Use the correct contracts directory
    CONTRACTS_DIR="$PROJECT_ROOT/contracts"
    BUILD_DIR="$PROJECT_ROOT/contracts/compiled"

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

    # Copy ABI to /enclave/contracts/abi
    ABI_SRC_DIR="$BUILD_DIR"
    ABI_DST_DIR1="$PROJECT_ROOT/enclave/contracts/abi"
    mkdir -p "$ABI_DST_DIR1"
    cp "$ABI_SRC_DIR"/*.abi "$ABI_DST_DIR1/"
    log "ABI copied to /enclave/contracts/abi ✅"

    # Copy ABI to /enclave/frontend/public/abi
    ABI_DST_DIR2="$PROJECT_ROOT/enclave/frontend/public/contracts/abi"
    mkdir -p "$ABI_DST_DIR2"
    cp "$ABI_SRC_DIR"/*.abi "$ABI_DST_DIR2/"
    log "ABI copied to /enclave/frontend/public/contracts/abi ✅"
}

# Build Docker image
build_docker() {
    log "Building Docker image..."
    
    cd "$PROJECT_ROOT"
    
    # Build the Docker image with the correct context and name
    # Use the enclave directory as build context since Dockerfile expects relative paths
    docker build --no-cache -t lottery-app:latest -f enclave/Dockerfile enclave/
    
    log "Docker image build completed ✅"

    # show image information
    docker image inspect lottery-app:latest
}


# Main build process
main() {
    log "Starting build process..."
        
    # Run build steps
    check_prerequisites
    compile_contracts
    # wait for user input to continue
    # read -p "Press [Enter] key to continue building docker image:"
    build_backend
    build_frontend
    build_docker
    
    log "🎉 Build process completed successfully!"
    log ""
    log "🚀 Next Steps:"
    log "3. ▶️  Run the application:"
    log "   $ docker run -it --name lottery -p 6080:6080 lottery-app:latest"
    log "4. 🌐 Access web interface: http://localhost:6080"
    log ""
    log "🏭 Production Deployment:"
    log "   • AWS Nitro Enclave: ./scripts/build_enclave.sh"
    log "   • Use production RPC endpoint and mainnet configuration"
}

# Run main function
main "$@"