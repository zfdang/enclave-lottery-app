# WebSocket Events

Authoritative description of the real-time events emitted by the backend.

Endpoint: `GET /ws` (websocket upgrade)
Format: Each message is a JSON object containing at minimum a `type` field.
Encoding: UTF-8 text frames.

## Event Types

| Type | Frequency | Purpose |
|------|-----------|---------|
| `round_update` | On poll cycle or round state change | Current round snapshot (timing, pot, winner, state) |
| `participants_update` | On poll cycle if changes detected | Aggregated participant bet totals |
| `history_update` | When a round completes / refunds | Recent historical rounds (capped) |
| `config_update` | On initial connect + periodic refresh | Contract config + derived parameters |

## round_update
Represents the current on-chain round (or absence if not initialized).

```jsonc
{
  "type": "round_update",
  "round": {
    "roundId": 12,
    "state": 2,              // numeric enum (see stateLabel)
    "stateLabel": "BETTING", // human-readable
    "startTime": 1733245000,
    "endTime": 1733245600,
    "minDrawTime": 1733245610,
    "maxDrawTime": 1733245800,
    "totalPotWei": "450000000000000000",   // stringified integer (wei)
    "participantCount": 14,
    "winner": null,          // or 0xabc... once drawn
    "publisherCommissionWei": "5000000000000000",
    "sparsityCommissionWei": "5000000000000000",
    "winnerPrizeWei": "440000000000000000"
  },
  "block": {
    "lastSeen": 19012345    // optional helper field if available
  }
}
```

## participants_update
Aggregated bet totals by participant for the active round.

```jsonc
{
  "type": "participants_update",
  "roundId": 12,
  "participants": [
    { "address": "0x1234...abcd", "totalAmountWei": "200000000000000000" },
    { "address": "0x9876...cdef", "totalAmountWei": "250000000000000000" }
  ],
  "participantCount": 14,
  "totalPotWei": "450000000000000000"
}
```

## history_update
Recent completed or refunded rounds (most recent first). Capacity controlled by `EVENTMGR_HISTORY_CAPACITY`.

```jsonc
{
  "type": "history_update",
  "rounds": [
    {
      "roundId": 11,
      "state": 4,
      "stateLabel": "COMPLETED",
      "winner": "0x9abC...1234",
      "totalPotWei": "300000000000000000",
      "winnerPrizeWei": "290000000000000000",
      "publisherCommissionWei": "5000000000000000",
      "sparsityCommissionWei": "5000000000000000",
      "endTime": 1733245200
    },
    {
      "roundId": 10,
      "state": 5,
      "stateLabel": "REFUNDED",
      "totalPotWei": "0",
      "endTime": 1733244800
    }
  ]
}
```

## config_update
Contract-defined parameters and any derived operator settings.

```jsonc
{
  "type": "config_update",
  "contract": {
    "publisherAddr": "0x1111...1111",
    "sparsityAddr": "0x2222...2222",
    "operatorAddr": "0x3333...3333",
    "publisherCommission": 100,  // basis points
    "sparsityCommission": 100,   // basis points
    "minBet": "10000000000000000",  // wei
    "bettingDuration": 600,          // seconds
    "minDrawDelay": 10,
    "maxDrawDelay": 300,
    "minEndTimeExtension": 5,
    "minParticipants": 2
  },
  "poll": {
    "intervalSeconds": 2,
    "configRefreshSeconds": 15
  }
}
```

## Connection Lifecycle

1. Client opens websocket → server immediately sends the latest snapshots (round, participants, history, config) in sequence.
2. Subsequent updates are incremental; clients should replace local state for each type by key (`round`, `participants`, etc.).
3. No explicit ping frames defined here; underlying server / proxy may inject heartbeats.

## Versioning & Compatibility

Currently unversioned. If payload shape changes, a new field `schemaVersion` will be added at the top level; clients should default to treating unknown fields as optional.

## Error Handling

Errors are not pushed as dedicated websocket messages; transport failure implies reconnect & full resync. If an error envelope is introduced it will use type `error` with `code` and `message` fields.

## Future Enhancements (Planned)
- Add `schemaVersion` early to future-proof
- Delta / patch events (reduce payload size for large participant lists)
- Integrity hash for `round` and `participants` arrays
- Heartbeat event (`type: heartbeat`) if intermediary proxies require application-level keepalive

---
This file reflects backend state serialization as of 2025-10-03.
