# Deployment Guide (Passive Lottery Operator)

This guide targets the current passive architecture: FastAPI web server + EventManager + PassiveOperator + BlockchainClient. Legacy demo scripts, engines, schedulers, and backup/database sections removed because the service is stateless (chain = source of truth).

## 1. Prerequisites
- Python 3.11+
- Node 18+ (building frontend locally; optional if using pre-built dist)
- Docker 20.10+ (for container packaging)
- (Optional) AWS Nitro Enclave capable EC2 instance for confidential deployment
- An Ethereum-compatible RPC (Anvil / Hardhat / testnet / mainnet)

## 2. Local Development

### 2.1 Clone
```bash
git clone <repo-url>
cd enclave-lottery-app
```

### 2.2 Environment (export minimal vars)
```bash
export BLOCKCHAIN_RPC_URL=http://127.0.0.1:8545
export BLOCKCHAIN_CHAIN_ID=31337
export BLOCKCHAIN_CONTRACT_ADDRESS=0xYourDeployedContract
export BLOCKCHAIN_OPERATOR_PRIVATE_KEY=0xYourOperatorKey
```
(Optional logging tweaks)
```bash
export APP_LOG_LEVEL=DEBUG
```

### 2.3 Backend deps
```bash
cd enclave
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### 2.4 Frontend (dev mode)
```bash
cd src/frontend
npm install
npm run dev
```
Visit the Vite dev URL; backend runs separately.

### 2.5 Run Backend
```bash
cd enclave
source venv/bin/activate
python src/main.py
```

## 3. Docker Deployment

### 3.1 Build
```bash
./scripts/build_docker.sh
```

### 3.2 Run
```bash
docker run --rm -p 6080:6080 \
  -e BLOCKCHAIN_RPC_URL=http://host.docker.internal:8545 \
  -e BLOCKCHAIN_CHAIN_ID=31337 \
  -e BLOCKCHAIN_CONTRACT_ADDRESS=0xYourDeployedContract \
  -e BLOCKCHAIN_OPERATOR_PRIVATE_KEY=0xYourOperatorKey \
  enclave-lottery-app:latest
```
If on Linux and connecting to host Anvil, ensure `--add-host host.docker.internal:host-gateway`.

### 3.3 Health
```bash
curl -f http://localhost:6080/health
```

## 4. AWS Nitro Enclave (High-Level)

1. Provision Nitro-capable EC2 (e.g. `m6i.large`) with enclave support enabled.
2. Install Docker + Nitro CLI.
3. Build enclave image file (EIF):
   ```bash
   ./scripts/build_enclave.sh
   ```
4. Run enclave:
   ```bash
   sudo nitro-cli run-enclave \
     --eif-path lottery.eif \
     --cpu-count 2 \
     --memory 1024 \
     --enclave-cid 16
   ```
5. If deploying in a Nitro Enclave, expose host↔enclave communication via a host-proxy component if required. The project does not provide an integrated vsock helper in the enclave runtime; implement the host proxy as a separate service.
6. Provide env vars to host process that relays into enclave (details depend on chosen proxy wiring).

(Full enclave attestation + vsock relay documentation will be expanded separately.)

## 5. Optional: Kubernetes
A simple Deployment + Service suffices. Inject sensitive values (operator key) via Secret → env var. Example sketch:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata: { name: lottery-operator }
spec:
  replicas: 1
  selector: { matchLabels: { app: lottery-operator } }
  template:
    metadata: { labels: { app: lottery-operator } }
    spec:
      containers:
        - name: operator
          image: your-registry/lottery:latest
          ports: [{ containerPort: 6080 }]
          env:
            - name: BLOCKCHAIN_RPC_URL
              value: https://rpc.example
            - name: BLOCKCHAIN_CHAIN_ID
              value: "11155111"
            - name: BLOCKCHAIN_CONTRACT_ADDRESS
              value: 0x123...
            - name: BLOCKCHAIN_OPERATOR_PRIVATE_KEY
              valueFrom:
                secretKeyRef:
                  name: operator-key
                  key: key
```
Add a Service:
```yaml
apiVersion: v1
kind: Service
metadata: { name: lottery-operator }
spec:
  selector: { app: lottery-operator }
  ports:
    - name: http
      port: 80
      targetPort: 6080
```

## 6. Observability
- Health: `GET /health`
- Logs: stdout (set `APP_LOG_LEVEL=DEBUG` for more detail; optional `APP_LOG_FILE` writes a file)
- Chain sync debug: look for log lines from `blockchain.client` about latest block + fetched logs.

## 7. Statelessness & Persistence
No database is used. History & feed caches in memory only. Durable history derives from chain events. Scaling horizontally requires an external pub/sub or consolidating to one instance (not currently implemented—document will be updated if that changes).

## 8. Troubleshooting
| Symptom | Checks |
|---------|--------|
| No websocket updates | Verify poll interval envs; check logs for ABI load; confirm contract address has code |
| Draw never triggers | Ensure operator key present; time window (min/max draw) reached; participant threshold met |
| Refund not sent | Verify contract state & elapsed max draw time; inspect operator logs for tx errors |
| RPC timeouts | Adjust network or set smaller `BLOCKCHAIN_GAS_MULTIPLIER`; verify RPC responsiveness |
| Contract config missing | Ensure EventManager config refresh interval running (log entries every ~N seconds) |

## 9. Security Notes
Implemented: minimal attack surface, non-root container, operator key never logged (redacted), reactive transaction submission only.
Planned / not yet: Attestation evidence surfacing endpoint, rate limiting, auth gating of any state‑changing endpoints (current UI interactions are all on‑chain via user wallets; backend only sends operator txs).

## 10. Variable Quick Reference
See `docs/CONFIG.md` for complete list. Minimum required for production:
```
BLOCKCHAIN_RPC_URL
BLOCKCHAIN_CHAIN_ID
BLOCKCHAIN_CONTRACT_ADDRESS
BLOCKCHAIN_OPERATOR_PRIVATE_KEY
```

## 11. Future Enhancements (Deployment)
- Horizontal scaling with shared state bus
- Structured metrics (Prometheus) endpoint
- Automated attestation validation service
- Blue/green contract migration procedure doc

---
Document scope intentionally minimal; expand only alongside implemented features.