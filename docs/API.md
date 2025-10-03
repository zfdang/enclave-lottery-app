# API Reference (Passive Operator)

Current backend exposes a minimal surface (subject to refinement). WebSocket (`/ws`) is the primary real-time channel.

Base URL (dev): `http://localhost:6080`

## Conventions
- All responses JSON
- Errors return non-2xx + JSON body `{ "error": "..." }`
- No authentication layer yet; read-only endpoints

## Endpoints

### GET /health
Returns liveness info and basic blockchain connectivity snapshot.
```json
{
  "status": "healthy",
  "blockchain": {
    "latestBlock": 19012345,
    "chainId": 31337
  },
  "version": "0.1.0"
}
```
Possible fields (some optional):
- `status`: `healthy` | `degraded` | `error`
- `blockchain.latestBlock`: most recent block known to client

### GET /status
Aggregated snapshot (denormalized convenience). Equivalent data also arrives over websocket events.
```json
{
  "round": { "roundId": 12, "state": 2, "stateLabel": "BETTING", "totalPotWei": "450000000000000000" },
  "participants": { "count": 14, "totalPotWei": "450000000000000000" },
  "config": { "minBetWei": "10000000000000000", "bettingDuration": 600 },
  "timestamp": 1733245055
}
```

### (Planned) GET /history
May be added if clients need historical snapshot without waiting for websocket burst.

### WebSocket /ws
See `docs/EVENTS.md` for schema. On connect the server pushes (in order): `config_update`, `round_update`, `participants_update`, `history_update` (when available).

## Errors
Standard structure (example):
```json
{ "error": "contract address not configured" }
```

## Rate Limiting
None implemented server-side. Upstream reverse proxy can enforce if needed.

## Versioning Strategy
Fields may be added (never removed) without version bump. Backwards incompatible changes will introduce a top-level `apiVersion` field in responses.

## Security Notes
- No private key material ever returned by any API.
- All state is reconstructable from chain (API is convenience + real-time channel).
- Add TLS termination (reverse proxy) for production.

## Future Additions (Planned)
- `/metrics` (Prometheus) endpoint
- Optional `/history` REST endpoint
- Health detail flags (poll loop latency, drift)
- `apiVersion` header or body field for contract-major upgrades

---
Reflects implementation state as of 2025-10-03.
