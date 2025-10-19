# 🐳 Docker Architecture (Passive Event-Driven Operator)

This document reflects the CURRENT container packaging after removal of the legacy Engine / Scheduler / BetManager stack. It intentionally omits unverified historical benchmark claims.

## Contents
- Overview
- Runtime Components
- Image Build Strategy
- Startup Flow
- Environment & Networking
- Operational Tasks
- Troubleshooting
- Maintenance Notes

---
## 1. Overview
A single container (or enclave base image) runs:
- FastAPI Web Server (REST + WebSocket)
- EventManager (polls contract + decodes logs)
- PassiveOperator (reacts to emitted `round_update` events; sends draw/refund txs)
- BlockchainClient (web3.py wrapper)
- Optional compiled frontend static assets (`dist/`)

No internal scheduler, cron, or engine state machine remains. All timing decisions derive from on‑chain round timestamps and participant counts.

## 2. Runtime Components
| Component | Path | Description |
|-----------|------|-------------|
| Web Server | `enclave/web_server.py` | REST endpoints, websocket broadcast, static assets (optional) |
| EventManager | `enclave/lottery/event_manager.py` | Poll round/participants/config, decode logs, publish events |
| PassiveOperator | `enclave/lottery/operator.py` | Decide draw vs refund and submit txs reactively |
| BlockchainClient | `enclave/blockchain/client.py` | Contract binding, view calls, log fetch, tx sending |
| Config Loader | `enclave/utils/config.py` | Layered file + env config, redaction |
| Logger | `enclave/utils/logger.py` | Central logging bootstrap |

### Event Flow
```
Ethereum Node ──(views/logs poll)──> EventManager ──> In‑Memory Store ──(fan‑out)──> WebSocket Clients
                                          │
                                          └──(round_update)──> PassiveOperator ──(tx)──> Chain
```

## 3. Image Build Strategy
Typical Dockerfile pattern (simplified example):
```dockerfile
FROM python:3.11-slim
RUN adduser --disabled-login --gecos '' lottery
WORKDIR /app
COPY enclave/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
# copy backend source
COPY enclave/ /app/
# (optional) copy pre-built frontend assets if you ran: npm run build
# COPY enclave/frontend/dist /app/frontend/dist
USER lottery
EXPOSE 6080
CMD ["python", "main.py"]
```
Key principles:
- Copy only what you need (compiled frontend not sources in prod image)
- Non‑root user (`lottery`)
- Deterministic dependency layer for cache efficiency

## 4. Startup Flow (Simplified)
1. Load config + init logging
2. Initialize `BlockchainClient` (connect; bind contract; prepare event ABI map)
3. Start EventManager polling loops (round/participants/config + log fetch)
4. Register PassiveOperator listener for `round_update`
5. Launch FastAPI server and websocket broadcast loop

Sequence (mermaid style – conceptual):
```
Container -> main.py -> BlockchainClient.init
main.py -> EventManager.start
EventManager -> PassiveOperator (subscribe round_update)
main.py -> WebServer.start (port 6080)
```

## 5. Environment & Networking
Environment variable namespaces (subset relevant to container):
- `BLOCKCHAIN_RPC_URL`, `BLOCKCHAIN_CHAIN_ID`, `BLOCKCHAIN_CONTRACT_ADDRESS`, `BLOCKCHAIN_OPERATOR_PRIVATE_KEY`
- `EVENTMGR_POLL_INTERVAL_SECONDS`, `EVENTMGR_HISTORY_CAPACITY`, `EVENTMGR_FEED_CAPACITY`
- `SERVER_HOST`, `SERVER_PORT`
- `APP_LOG_LEVEL`, `APP_LOG_FILE` (optional)

Example run:
```bash
docker run --rm -p 6080:6080 \
  -e BLOCKCHAIN_RPC_URL=http://host.docker.internal:8545 \
  -e BLOCKCHAIN_CHAIN_ID=31337 \
  -e BLOCKCHAIN_CONTRACT_ADDRESS=0x5FbDB2315678afecb367f032d93F642f64180aa3 \
  -e BLOCKCHAIN_OPERATOR_PRIVATE_KEY=0xac09...f80 \
  enclave-lottery-app:latest
```

If the container must reach a host Anvil node on Linux, add:
```
--add-host host.docker.internal:host-gateway
```

Health probe (example – align with actual implementation):
```bash
curl -f http://localhost:6080/health
```

## 6. Operational Tasks
| Task | Command |
|------|---------|
| View logs | `docker logs -f lottery` |
| Exec shell (debug) | `docker exec -it lottery /bin/sh` |
| Inspect env | `docker inspect lottery` |
| Follow health | `watch -n2 curl -sf localhost:6080/health` |

## 7. Troubleshooting
### Blockchain connection failures
Symptoms: repeated warnings about RPC connectivity.
Actions:
1. Verify RPC reachable from host: `curl -sf host.docker.internal:8545` (or your URL)
2. Ensure correct chain id (log will warn on mismatch)
3. Check for firewall / Docker network isolation issues

### No websocket events
1. Confirm EventManager poll interval vars are set (defaults apply if unset)
2. Check logs for contract ABI load problems
3. Ensure contract address has code (client logs an error if empty)

### Draws not occurring
1. Verify `round_update` shows current block timestamps within draw window
2. Confirm operator private key configured (logs: "Operator account loaded")
3. Check for tx send errors (gas estimation or nonce conflicts)

### Container exits immediately
Likely unhandled exception during startup; inspect `docker logs` for root cause (config parse, RPC unreachable, missing ABI file).

## 8. Security Notes (Container Scope)
Implemented:
- Non‑root user
- Minimal copied assets
- Private key only passed via env (redacted in logs)
Planned / external to container doc:
- Full attestation exposition (Nitro)
- Enhanced secrets management (KMS / AWS Secrets Manager)

## 9. Maintenance Notes
- Keep this doc consistent with `README.md` and the passive operator philosophy
- When adding endpoints or events, cross‑link to `docs/API.md` and `docs/EVENTS.md`
- Reintroduce metrics only with reproducible methodology (CI benchmarks)

_Last updated: 2025-10-03 (passive architecture alignment)_