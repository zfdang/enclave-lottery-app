#!/bin/bash
# Lottery System Demo - Main Entry Point
# Simplified launcher for the consolidated demo system

set -e

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${CYAN}"
echo "  ╔══════════════════════════════════════════════════╗"
echo "  ║          🎰 Lottery System Demo 🎰              ║"
echo "  ║     Comprehensive Demo Suite - v2.0            ║"
echo "  ╚══════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${GREEN}Starting unified demo system...${NC}"
echo

# Change to project directory
cd "$(dirname "$0")"

# Set Python path and run the consolidated demo
export PYTHONPATH="${PWD}/enclave/src:${PYTHONPATH}"
python3 lottery_demo.py

echo
echo -e "${YELLOW}Demo session ended. Thank you for using Lottery System Demo!${NC}"