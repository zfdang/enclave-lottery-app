#!/bin/bash

# AWS Nitro Enclave Lottery App Build Script
set -e

echo "Building Lottery Enclave Application..."

# Configuration
ENCLAVE_NAME="lottery-enclave"
DOCKER_IMAGE_NAME="enclave-lottery-app"
EIF_FILE="lottery.eif"
CPU_COUNT=2
MEMORY_SIZE=1024

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running on EC2 instance with Nitro Enclave support
check_nitro_support() {
    print_status "Checking Nitro Enclave support..."
    
    if ! which nitro-cli > /dev/null 2>&1; then
        print_error "nitro-cli not found. Please install AWS Nitro CLI."
        exit 1
    fi
    
    # skip this change, since this code does not work in amazon linux 2023
    # if ! lsmod | grep -q nitro_enclaves; then
    #     print_error "Nitro Enclaves kernel module not loaded."
    #     print_warning "Run: sudo modprobe nitro_enclaves"
    #     exit 1
    # fi
    
    print_status "Nitro Enclave support verified."
}

# Build Docker image
build_docker_image() {
    print_status "Building Docker image..."
    # Build the Docker image using the enclave directory as build context
    # This matches the approach used in build_docker.sh for consistency
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    REPO_ROOT="$(dirname "$SCRIPT_DIR")"

    # Use enclave directory as build context since Dockerfile expects relative paths
    cd "$REPO_ROOT"
    docker build -t ${DOCKER_IMAGE_NAME}:latest -f enclave/Dockerfile enclave/
    
    if [ $? -eq 0 ]; then
        print_status "Docker image built successfully: ${DOCKER_IMAGE_NAME}:latest"
    else
        print_error "Failed to build Docker image"
        exit 1
    fi
}

# Build Enclave Image File (EIF)
build_eif() {
    print_status "Building Enclave Image File..."
    
    # Build EIF from Docker image
    nitro-cli build-enclave \
        --docker-uri ${DOCKER_IMAGE_NAME}:latest \
        --output-file ${EIF_FILE}
    
    if [ $? -eq 0 ]; then
        print_status "EIF built successfully: ${EIF_FILE}"
        
        # Show EIF information
        nitro-cli describe-eif --eif-path ${EIF_FILE}
    else
        print_error "Failed to build EIF"
        exit 1
    fi
}

# Allocate resources for enclave
allocate_resources() {
    print_status "Allocating enclave resources..."
    # Allocate CPUs and memory for enclave if the installed nitro-cli supports it.
    if ! command -v nitro-cli >/dev/null 2>&1; then
        print_warning "nitro-cli not found; skipping resource allocation."
        return
    fi

    # Some nitro-cli versions do not have an 'allocate-enclave' subcommand.
    if nitro-cli help 2>&1 | grep -q "allocate-enclave"; then
        print_status "Attempting to allocate resources with nitro-cli..."
        if sudo nitro-cli allocate-enclave \
            --cpu-count ${CPU_COUNT} \
            --memory ${MEMORY_SIZE}; then
            print_status "Resources allocated: ${CPU_COUNT} CPUs, ${MEMORY_SIZE}MB memory"
        else
            print_warning "Failed to allocate resources (may already be allocated or insufficient privileges)"
        fi
    else
        print_warning "Installed nitro-cli does not support 'allocate-enclave'. Skipping allocation."
        print_warning "You can start enclaves directly with 'nitro-cli run-enclave' when needed."
    fi
}

# Run enclave (optional)
run_enclave() {
    if [ "$1" = "--run" ]; then
        print_status "Starting enclave..."
        
        # Run the enclave
        ENCLAVE_ID=$(sudo nitro-cli run-enclave \
            --eif-path ${EIF_FILE} \
            --cpu-count ${CPU_COUNT} \
            --memory ${MEMORY_SIZE} \
            --enclave-cid 16 \
            --debug-mode \
            | jq -r '.EnclaveId')
        
        if [ $? -eq 0 ] && [ "$ENCLAVE_ID" != "null" ]; then
            print_status "Enclave started with ID: ${ENCLAVE_ID}"
            print_status "To view enclave console: sudo nitro-cli console --enclave-id ${ENCLAVE_ID}"
            print_status "To stop enclave: sudo nitro-cli terminate-enclave --enclave-id ${ENCLAVE_ID}"
        else
            print_error "Failed to start enclave"
            exit 1
        fi
    fi
}

# Main execution
main() {
    print_status "Starting build process for Lottery Enclave Application"
    
    # Check prerequisites
    check_nitro_support
    
    # Build steps
    build_docker_image
    build_eif
    allocate_resources
    run_enclave $1
    
    print_status "Build completed successfully!"
    print_status "EIF file: ${EIF_FILE}"
    print_status "Use 'sudo nitro-cli run-enclave --eif-path ${EIF_FILE} --cpu-count ${CPU_COUNT} --memory ${MEMORY_SIZE} --enclave-cid 16' to run"
}

# Handle script arguments
case "${1:-}" in
    --run)
        main --run
        ;;
    --help|-h)
        echo "Usage: $0 [--run] [--help]"
        echo ""
        echo "Options:"
        echo "  --run     Build and immediately run the enclave"
        echo "  --help    Show this help message"
        echo ""
        echo "This script builds the Lottery Enclave application and creates an EIF file."
        exit 0
        ;;
    *)
        main
        ;;
esac