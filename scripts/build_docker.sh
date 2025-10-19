#!/bin/bash

# Lottery Enclave Build Script
# This script builds a complete, production-ready lottery application Docker image.
# Features: optimized frontend build, selective file copying, proper permissions, and .env validation.
# The resulting Docker image excludes unnecessary development files for minimal size and security.

set -euo pipefail

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
    log "Step 1: Checking prerequisites..."

    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed. Please install Docker first."
        exit 1
    else
        log "Docker: $(docker --version)"
    fi

    # Check if Node.js is installed (frontend build)
    SKIP_FRONTEND=0
    if ! command -v node &> /dev/null; then
        warning "Node.js is not installed. Frontend build will be skipped."
        SKIP_FRONTEND=1
    else
        log "Node.js: $(node --version)"
    fi

    # Check if Python is available (backend prep)
    if ! command -v python3 &> /dev/null; then
        error "Python 3 is not installed. Backend build cannot proceed."
        exit 1
    else
        log "Python: $(python3 --version)"
    fi

    log "Prerequisites check completed ✅"
    export SKIP_FRONTEND
}

# Print operator key setup reminder
print_operator_key_reminder() {
    log "Step 2: Operator private key setup"
    echo -e "${YELLOW}⚠️  IMPORTANT: After deploying the application, you must set the operator private key.${NC}"
    echo -e "${YELLOW}   Use the key injection script: ./scripts/set_operator_key.py${NC}"
    echo -e "${YELLOW}   DO NOT commit private keys to source control!${NC}"
}

# Build frontend
build_frontend() {
    log "Step 4: Building React frontend (if available)..."

    # Honor SKIP_FRONTEND exported by check_prerequisites
    if [[ "${SKIP_FRONTEND:-0}" == "1" ]]; then
        warning "Skipping frontend build because Node.js is not available."
        return
    fi

    cd "$PROJECT_ROOT/enclave/frontend"

    # check .env file exists, if it doesn't, suggest user to copy .env.example
    if [[ ! -f ".env" ]]; then
        error ".env file not found in frontend directory. Please copy .env.example to .env and configure it."
        exit 1
    fi

    # Install dependencies
    if [[ ! -d "node_modules" ]]; then
        log "Installing npm dependencies..."
        npm install
    fi

    # Build production frontend
    log "Running: npm run build"
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
    log "Step 6: Building Docker image..."

    cd "$PROJECT_ROOT"

    # Build the Docker image with the correct context and name
    log "Running: docker build --no-cache -t lottery-app:latest -f enclave/Dockerfile enclave/"
    docker build --no-cache -t lottery-app:latest -f enclave/Dockerfile enclave/

    log "Docker image build completed ✅"

    # show image information
    docker image inspect lottery-app:latest || true
}


# Main build process
main() {
    log "Starting build process..."

    START_ALL=$(date +%s)

    # Run build steps with clear numbering
    check_prerequisites
    
    # Remind user about operator key
    print_operator_key_reminder

    STEP=3; STEP_START=$(date +%s); log "Step $STEP: Compiling smart contracts..."; compile_contracts; log "Step $STEP completed in $(( $(date +%s) - STEP_START ))s"

    STEP=4; STEP_START=$(date +%s); log "Step $STEP: Preparing Python backend..."; build_backend; log "Step $STEP completed in $(( $(date +%s) - STEP_START ))s"

    STEP=5; STEP_START=$(date +%s); log "Step $STEP: Building frontend (optional)..."; build_frontend; log "Step $STEP completed in $(( $(date +%s) - STEP_START ))s"

    STEP=6; STEP_START=$(date +%s); log "Step $STEP: Building Docker image..."; build_docker; log "Step $STEP completed in $(( $(date +%s) - STEP_START ))s"

    log "🎉 Build process completed successfully in $(( $(date +%s) - START_ALL ))s!"
    log ""
    log "🚀 Next Steps:"
    log "1. ▶️  Run the application:"
    log "   $ docker run --rm -it --name lottery -p 6080:6080 lottery-app:latest"
    log ""
    log "2. 🔐 Set operator private key (REQUIRED):"
    log "   $ python3 scripts/set_operator_key.py"
    log "   (This securely injects the operator key into the running enclave)"
    log ""
    log "3. 🌐 Access web interface: http://localhost:6080"
    log ""
    log "🏭 Enclave Deployment:"
    log "   $ enclaver build -f enclave/enclaver.yaml"
    log "   $ enclaver run --publish 6080:6080 enclave-lottery-app:latest"
}

# Provide a trap so failures print a helpful message
on_error() {
    error "Build failed at step. See output above for details."
}
trap on_error ERR

# Run main function
main "$@"