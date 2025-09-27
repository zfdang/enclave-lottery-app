#!/usr/bin/env bash
# Lightweight launcher to run the passive operator app with correct PYTHONPATH
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${SCRIPT_DIR}/.."
export PYTHONPATH="${ROOT_DIR}/enclave/src:${PYTHONPATH-}"
# Run main as a module so imports resolve; this will start the app normally.
python3 -m main "$@"
