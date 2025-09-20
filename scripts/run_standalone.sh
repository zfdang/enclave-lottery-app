#!/bin/bash
# Deprecated: Standalone runner has been consolidated into the unified demo.

set -e

YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}This script is deprecated. Please use the unified demo instead:${NC}"
echo
echo "  ./demo.sh"
echo "    - or -"
echo "  python3 lottery_demo.py"
echo
echo -e "${YELLOW}Tip:${NC} For the web-based demo, use: scripts/comprehensive_demo.sh"
exit 0