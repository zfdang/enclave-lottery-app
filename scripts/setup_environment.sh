#!/bin/bash

# Setup AWS Environment for Lottery Enclave
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

# Check if running on EC2
check_ec2_instance() {
    print_status "Checking if running on EC2 instance..."
    
    if ! curl -s -m 5 http://169.254.169.254/latest/meta-data/instance-id > /dev/null; then
        print_error "This script must be run on an EC2 instance"
        exit 1
    fi
    
    print_status "EC2 instance confirmed"
}

# Check instance type for Nitro Enclave support
check_instance_type() {
    print_status "Checking instance type for Nitro Enclave support..."
    
    INSTANCE_TYPE=$(curl -s http://169.254.169.254/latest/meta-data/instance-type)
    print_status "Instance type: ${INSTANCE_TYPE}"
    
    # List of Nitro Enclave supported instance types
    SUPPORTED_TYPES=("m5.large" "m5.xlarge" "m5.2xlarge" "m5.4xlarge" "m5.8xlarge" "m5.12xlarge" "m5.16xlarge" "m5.24xlarge"
                     "m5d.large" "m5d.xlarge" "m5d.2xlarge" "m5d.4xlarge" "m5d.8xlarge" "m5d.12xlarge" "m5d.16xlarge" "m5d.24xlarge"
                     "m5n.large" "m5n.xlarge" "m5n.2xlarge" "m5n.4xlarge" "m5n.8xlarge" "m5n.12xlarge" "m5n.16xlarge" "m5n.24xlarge"
                     "r5.large" "r5.xlarge" "r5.2xlarge" "r5.4xlarge" "r5.8xlarge" "r5.12xlarge" "r5.16xlarge" "r5.24xlarge"
                     "c5.large" "c5.xlarge" "c5.2xlarge" "c5.4xlarge" "c5.9xlarge" "c5.12xlarge" "c5.18xlarge" "c5.24xlarge"
                     "c5n.large" "c5n.xlarge" "c5n.2xlarge" "c5n.4xlarge" "c5n.9xlarge" "c5n.18xlarge")
    
    if [[ " ${SUPPORTED_TYPES[@]} " =~ " ${INSTANCE_TYPE} " ]]; then
        print_status "Instance type supports Nitro Enclaves"
    else
        print_warning "Instance type ${INSTANCE_TYPE} may not support Nitro Enclaves"
        print_warning "Supported types include: m5.*, m5d.*, m5n.*, r5.*, c5.*, c5n.*"
    fi
}

# Install AWS Nitro CLI
install_nitro_cli() {
    print_status "Installing AWS Nitro CLI..."
    
    # Check if already installed
    if which nitro-cli > /dev/null 2>&1; then
        print_status "Nitro CLI already installed"
        nitro-cli --version
        return
    fi
    
    # Install dependencies
    sudo yum update -y
    sudo yum install -y aws-nitro-enclaves-cli aws-nitro-enclaves-cli-devel
    
    # Verify installation
    if which nitro-cli > /dev/null 2>&1; then
        print_status "Nitro CLI installed successfully"
        nitro-cli --version
    else
        print_error "Failed to install Nitro CLI"
        exit 1
    fi
}

# Install Docker
install_docker() {
    print_status "Installing Docker..."
    
    # Check if already installed
    if which docker > /dev/null 2>&1; then
        print_status "Docker already installed"
        docker --version
        return
    fi
    
    # Install Docker
    sudo yum install -y docker
    sudo systemctl start docker
    sudo systemctl enable docker
    
    # Add user to docker group
    sudo usermod -aG ne ec2-user
    sudo usermod -aG docker ec2-user

    print_status "Docker installed successfully"
    print_warning "Please log out and log back in for group changes to take effect"
}

# Install Node.js and npm
install_nodejs() {
    print_status "Installing Node.js and npm..."
    
    # Check if already installed
    if which node > /dev/null 2>&1; then
        print_status "Node.js already installed"
        node --version
        npm --version
        return
    fi
    
    # Install Node.js
    curl -fsSL https://rpm.nodesource.com/setup_18.x | sudo bash -
    sudo yum install -y nodejs
    
    print_status "Node.js and npm installed successfully"
    node --version
    npm --version
}

# Install Python 3.9
install_python() {
    print_status "Installing Python 3.9..."
    
    # Check if Python 3.9 is available
    if python3 --version > /dev/null 2>&1; then
        print_status "Python 3 already installed"
        python3 --version
    else
        print_status "Python 3 not found, proceeding with installation"
        # install python3 through dnf
        sudo yum install -y python3
        print_status "Python 3 installed successfully"
        python3 --version
    fi

    # Check if pip3 is available
    if pip3 --version > /dev/null 2>&1; then
        print_status "pip3 already installed"
        pip3 --version
    else
        print_status "pip3 not found, proceeding with installation"
        # install pip3 through dnf
        sudo yum install -y python3-pip
        print_status "pip3 installed successfully"
        pip3 --version
    fi

    
    # Install Python 3.9
    print_status "Installing Python3-devel via yum..."
    sudo yum install -y python3-devel

    print_status "Python 3 installed successfully"
    python3 --version
    pip3 --version
}

# Configure Nitro Enclaves
configure_nitro_enclaves() {
    print_status "Configuring Nitro Enclaves..."
    
    # Enable and start the nitro-enclaves-allocator service
    sudo systemctl enable nitro-enclaves-allocator.service
    sudo systemctl start nitro-enclaves-allocator.service
    
    # Enable and start the docker service
    sudo systemctl enable docker.service
    sudo systemctl start docker.service
    
    print_status "Nitro Enclaves configured successfully"
}

# configure solidity development environment
configure_solidity() {
    print_status "Configuring Solidity development environment..."
    
    # Check if solc-select is already installed
    if which solc-select > /dev/null 2>&1; then
        print_status "solc-select already installed"
        solc-select --version
    else
        print_status "Installing solc-select..."
        
        # Install solc-select via pip
        pip3 install --user solc-select
        
        # Ensure ~/.local/bin is in PATH for this session
        export PATH=$PATH:~/.local/bin
        
        if which solc-select > /dev/null 2>&1; then
            print_status "solc-select installed successfully"
        else
            print_error "Failed to install solc-select"
            exit 1
        fi
    fi
    
    # Install a stable Solidity version (0.8.19 is widely used and stable)
    print_status "Installing Solidity compiler version 0.8.19..."
    solc-select install 0.8.19
    
    # Set the default version
    print_status "Setting Solidity 0.8.19 as default..."
    solc-select use 0.8.19
    
    # Verify installation
    if which solc > /dev/null 2>&1; then
        print_status "Solidity compiler configured successfully"
        solc --version
    else
        print_warning "Solidity compiler not found in PATH. You may need to restart your shell."
    fi
    
    # Optional: Install additional common versions
    print_status "Installing additional Solidity versions..."
    solc-select install 0.8.20 || print_warning "Failed to install Solidity 0.8.20"
    solc-select install 0.8.21 || print_warning "Failed to install Solidity 0.8.21"
    
    # Show available versions
    print_status "Available Solidity versions:"
    solc-select versions
    
    print_status "Solidity development environment configured successfully"
}


# Set up environment
setup_environment() {
    print_status "Setting up environment..."
        
    # Set environment variables
    echo 'export PATH=$PATH:~/.local/bin' >> ~/.bashrc
    
    print_status "Environment setup completed"
}

# Main setup function
main() {
    print_status "Starting AWS environment setup for Lottery Enclave"
    
    check_ec2_instance
    check_instance_type
    install_nitro_cli
    configure_nitro_enclaves

    install_docker
    install_nodejs
    install_python
    configure_solidity
    setup_environment
    
    print_status "Setup completed successfully!"
    print_warning "Please log out and log back in to apply group membership changes"
    print_status "After re-login, you can build the enclave with: ./scripts/build_enclave.sh"
}

# Run main function
main