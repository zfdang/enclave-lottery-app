# Development Guide

This guide summarizes local development workflows, the consolidated demo system, and helpful scripts.

## Prerequisites
- Node.js 18+
- Python 3.11+

## Frontend
- Location: `enclave/src/frontend`
- Scripts:
  - `npm install`
  - `npm run dev` (Vite dev server)
  - `npm run build` (production build → `dist/`)

## Backend (FastAPI)
- Location: `enclave/src`
- Entrypoints:
  - `enclave/src/main.py` (production-style)
  - `enclave/demo_app.py` (demo web server + scenarios)

Create a venv and install dependencies:

```bash
cd enclave
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Run demo server:
```bash
python demo_app.py
```

## Unified Demo
- Launcher: `./demo.sh`
- Core: `lottery_demo.py`
- Web-centric: `scripts/comprehensive_demo.sh`

Recommended usage:
```bash
./demo.sh
```

## Testing & Utilities
- `scripts/test_app.sh` includes a syntax/availability check for `scripts/comprehensive_demo.sh`.
- `test_web_server.py` can start a simple API server for manual testing.

## Consolidation Notes
- Deprecated/removed:
  - `web_only.py` (removed)
  - `test_comprehensive_demo.sh` (merged into `scripts/test_app.sh`)
  - `scripts/run_standalone.sh` (deprecated stub)
  - `enclave/quick_demo.py` (stub pointing to `demo.sh`)