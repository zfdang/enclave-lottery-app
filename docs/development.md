# Development Guide (Passive Architecture)

Focused on the lean runtime (FastAPI + EventManager + PassiveOperator). Legacy demo launchers and engine/scheduler tooling have been removed.

## Prerequisites
- Node.js 18+
- Python 3.11+

## Frontend
Location: `enclave/src/frontend`

Common scripts:
* `npm install` – install deps
* `npm run dev` – Vite dev server (hot reload)
* `npm run build` – production bundle → `dist/`
* `npm run preview` – serve built assets locally

## Backend
Location: `enclave/src`

Entry point: `enclave/src/main.py`

Key modules:
* `lottery/event_manager.py` – polling + event serialization
* `lottery/operator.py` – passive draw/refund logic
* `blockchain/client.py` – contract interaction
* `utils/config.py` / `utils/logger.py`

Create a venv and install dependencies:

```bash
cd enclave
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Run backend:
```bash
python src/main.py
```

## WebSocket Event Inspection
Start backend with `APP_LOG_LEVEL=DEBUG` to view poll & event emission logs. Use browser dev tools or `wscat`:
```bash
wscat -c ws://localhost:6080/ws
```

## Testing (Suggested Additions)
Currently limited automated coverage. Recommended to add:
* Unit tests for operator timing decisions (draw vs refund)
* Event serialization snapshot tests
* Lightweight health endpoint test

Example (placeholder):
```bash
pytest -k operator -v
```

## Removed Legacy Artifacts
Eliminated for clarity:
* Demo orchestration scripts (`demo.sh`, quick demo variants)
* Engine/scheduler modules
* Hard-coded timed draw loops

New contributions should avoid reintroducing implicit schedulers—derive actions solely from chain state emissions.

---
See also: `README.md`, `docs/CONFIG.md`, docs (upcoming) `API.md`, `EVENTS.md`.