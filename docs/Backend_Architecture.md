# Backend Architecture

## Component Interaction Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          BLOCKCHAIN                                  │
│  (Lottery Contract - Events: RoundCreated, BetPlaced, etc.)         │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             │ RPC Calls (Polling & Transactions)
                             ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      BLOCKCHAIN CLIENT                               │
│  • get_events(from_block)                                           │
│  • get_current_round()                                              │
│  • get_participant_summaries()                                      │
│  • get_contract_config()                                            │
│  • draw_round() / refund_round()                                    │
└──────┬──────────────────────────────────────────────┬───────────────┘
       │                                              │
       │ Read State                                   │ Write Txs
       ↓                                              │
┌─────────────────────────────────────────────────────┼───────────────┐
│                    EVENT MANAGER                    │               │
│  • Poll blockchain for events (configurable)       │               │
│  • Refresh round state every 2s                    │               │
│  • Refresh contract config every 20s               │               │
│  • Update MemoryStore with latest data             │               │
│  • Emit blockchain_event to listeners              │               │
│  • Add events to live activity feed                │               │
│  • Create round history snapshots                  │               │
└──────┬──────────────────────────────────────────────┘               │
       │                                                               │
       │ Events (via MemoryStore._emit)                               │
       ↓                                                               │
┌─────────────────────────────────────────────────────────────────────┤
│                    MEMORY STORE                                     │
│  • Current round state                                              │
│  • Participants list                                                │
│  • Round history                                                    │
│  • Live activity feed                                               │
│  • Contract config                                                  │
│  • Event listeners registry                                         │
└──────┬──────────────────────────────────────────────┬───────────────┘
       │                                              │
       │ Read State                                   │ Read State
       │ Listen to Events                             │
       ↓                                              ↓
┌─────────────────────────────────────────┐  ┌──────────────────────┐
│         PASSIVE OPERATOR                │  │    WEB SERVER        │
│  • Listen to round_update events        │  │  • HTTP API          │
│  • React to draw/refund windows         │  │  • WebSocket feed    │
│  • Execute draws in time window         │  │  • Serve frontend    │
│  • Execute refunds when expired         │  │                      │
│  • Retry failed transactions            │  │                      │
└──────────────────┬──────────────────────┘  └──┬───────────────────┘
                   │                            │
                   │ Blockchain Write Calls     │
                   └────────────────────────────┘
                                │
                                ↓
                   ┌────────────────────────────┐
                   │    BLOCKCHAIN CLIENT       │
                   │  • draw_round()            │
                   │  • refund_round()          │
                   └────────────────────────────┘
```

## Event Flow: Round Creation

```
1. Contract emits RoundCreated event
   ↓
2. EventManager polls blockchain and detects event
   ↓
3. EventManager updates MemoryStore:
   - store.set_current_round(round_data)
   - store.add_live_feed(event_message)
   ↓
4. MemoryStore emits `round_update` with the serialized round payload
   ↓
5. PassiveOperator receives `round_update` via callback
   ↓
6. Operator evaluates current time against `minDrawTime` / `maxDrawTime` and acts immediately:
   - If inside the draw window, call `blockchain_client.draw_round()` and wait for confirmation
   - If past the draw window, call `blockchain_client.refund_round()`
```

## Event Flow: State Refresh

```
1. EventManager timer fires (every 2s for round state)
   ↓
2. EventManager queries blockchain_client:
   - get_current_round()
   - get_participant_summaries()
   ↓
3. EventManager updates MemoryStore:
   - store.set_current_round(round_data)
   - store.sync_participants(participants)
   ↓
4. MemoryStore emits update events:
   - _emit("round_update", payload)
   - _emit("participants_update", payload)
   ↓
5. WebSocket listeners receive updates via WebServer
   ↓
6. Frontend UI auto-refreshes with new data
```

## Architectural Principles

### Component Responsibilities

**EventManager** (Data Synchronization Layer)
- Single source of blockchain polling
- Maintains fresh state in MemoryStore
- Emits events for state changes
- Manages live activity feed
- Creates round history snapshots

**PassiveOperator** (Business Logic Layer)
- Event-driven draw/refund handler
- Subscribes to `round_update` events emitted by MemoryStore
- Makes idempotent decisions directly from serialized round payloads
- Executes draws within contract time windows (minDrawTime ~ maxDrawTime)
- Executes refunds when rounds expire
- Handles transaction retries and failures

**MemoryStore** (State & Pub/Sub Layer)
- Central state repository
- Event distribution hub
- Supports multiple listeners
- Thread-safe access

**WebServer** (Presentation Layer)
- HTTP REST API
- WebSocket real-time feed
- Serves frontend application

### Data Flow Patterns

**Read Path:**
```
Blockchain → EventManager → MemoryStore → (Operator / WebServer)
```

**Write Path:**
```
Operator → BlockchainClient → Blockchain → EventManager (detects change)
```

**Event Distribution:**
```
EventManager → MemoryStore._emit() → Registered Listeners
```

## Draw Timing Logic

The operator follows the contract's time window requirements:

### Time Phases

**1. Before Draw Window** (`now < minDrawTime`)
- Operator waits, no action taken
- Logs: "waiting for draw window (starts in Xs)"

**2. Draw Window** (`minDrawTime <= now <= maxDrawTime`)
- **Only time period when draws are allowed**
- Operator attempts `drawWinner()` transaction
- Contract validates timestamp and executes draw
- Logs: "inside draw window [min, max], attempting draw"

**3. After Draw Window** (`now > maxDrawTime`)
- Draw opportunity expired
- Operator calls `refundRound()` immediately
- Returns bets to all participants
- Logs: "draw window expired at X, attempting refund"

### Round Update Handling

When a new round is created or refreshed:
1. EventManager detects on-chain changes and updates MemoryStore
2. MemoryStore emits a `round_update` payload with serialized round fields
3. PassiveOperator receives the payload, reads `minDrawTime` / `maxDrawTime`, and:
   - If the draw window has not opened yet, it simply waits for the next update
   - If the draw window is open, it submits the draw transaction immediately
   - If the window has expired, it submits a refund transaction immediately

### Retry Logic

If a draw or refund transaction fails the operator logs the error. Because there is no scheduler loop, retries rely on either:
- A subsequent `round_update` emission while the round remains in the draw window, or
- Manual intervention (triggering a draw/refund via API or CLI)

## Error Handling

### EventManager Failure
- MemoryStore data becomes stale
- PassiveOperator holds the last payload but receives no new `round_update` events
- No additional draw/refund actions are triggered until EventManager recovers
- Frontend data stops refreshing; manual monitoring recommended

### Operator Failure
- EventManager continues updating state
- WebSocket clients receive updates normally
- Draws won't be executed automatically
- Manual draw/refund via API still possible

### MemoryStore Failure
- Both EventManager and Operator affected
- Application restart required
- State rebuilt from blockchain on startup

### Blockchain RPC Failure
- EventManager retries with exponential backoff
- Operator transactions fail and retry
- Frontend shows connection status
- System recovers when RPC available

## Performance Characteristics

**Polling Intervals:**
- Events: Configurable (default: frequent via eth_getLogs)
- Round state: Every 2 seconds
- Contract config: Every 20 seconds

**RPC Load:**
- ~60 event polls per minute
- ~30 round state refreshes per minute
- ~3 config refreshes per minute
- Total: ~93 read calls/min + transaction writes

**Latency:**
- Event detection: < 2s (polling interval)
- State propagation: < 100ms (in-memory)
- WebSocket updates: Real-time (< 10ms)
- Draw execution: ~15s (transaction confirmation)

## Configuration

### OperatorSettings

```python
tx_timeout_seconds: int = 180          # Transaction confirmation timeout
```

Legacy scheduler-related parameters (`draw_check_interval`, `draw_retry_delay`, `max_draw_retries`) were removed along with the OperatorStatus state machine.

### EventManager Settings

```python
contract_config_interval_sec: int = 20          # Config refresh interval
round_and_participants_interval_sec: int = 2    # Round state refresh interval
event_source: str = "eth_getLogs"               # Event polling method
start_block_offset: int = 500                   # Initial history lookback
live_feed_max_entries: int = 1000               # Activity feed size
round_history_max: int = 20                     # Completed rounds to keep
```

## Summary

The backend uses an **event-driven architecture** where:
- **EventManager** is the single source of blockchain data
- **MemoryStore** serves as the central state repository and pub/sub hub
- **PassiveOperator** reacts to events and manages draw/refund logic
- **WebServer** exposes data to frontend clients

This design ensures:
- No duplicate blockchain polling
- Clear separation of concerns
- Real-time updates via WebSocket
- Scalable event distribution
- Testable components