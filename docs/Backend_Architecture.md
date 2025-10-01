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
│  • Operator status                                                  │
│  • Event listeners registry                                         │
└──────┬──────────────────────────────────────────────┬───────────────┘
       │                                              │
       │ Read State                                   │ Read State
       │ Listen to Events                             │
       ↓                                              ↓
┌─────────────────────────────────────────┐  ┌──────────────────────┐
│         PASSIVE OPERATOR                │  │    WEB SERVER        │
│  • Listen to blockchain_event           │  │  • HTTP API          │
│  • Schedule draws when rounds ready     │  │  • WebSocket feed    │
│  • Execute draws in time window         │  │  • Serve frontend    │
│  • Execute refunds when expired         │  │                      │
│  • Retry failed transactions            │  │                      │
│  • Update operator status               │  │                      │
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
4. EventManager emits blockchain_event:
   store._emit("blockchain_event", {
     "event": evt,
     "name": "RoundCreated",
     "args": {"roundId": 1, ...}
   })
   ↓
5. PassiveOperator receives event via callback:
   _on_blockchain_event(payload) → _handle_event(event)
   ↓
6. Operator schedules draw:
   - Reads round data from MemoryStore
   - Calculates draw time (max(minDrawTime, now))
   - Updates operator status with scheduled draw
   ↓
7. Draw loop periodically checks scheduled draws
   ↓
8. When minDrawTime <= now <= maxDrawTime:
   - Operator calls blockchain_client.draw_round()
   - Waits for transaction confirmation
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
- Event-driven draw management
- Executes draws within contract time windows (minDrawTime ~ maxDrawTime)
- Executes refunds when rounds expire
- Handles transaction retries and failures
- No direct blockchain polling

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

### Draw Scheduling

When a new round is created:
1. EventManager detects `RoundCreated` event
2. Emits `blockchain_event` to operator
3. Operator schedules draw at `max(minDrawTime, currentTime)`
4. Draw loop checks every 10s (configurable)
5. When time window arrives, executes draw

### Retry Logic

If draw transaction fails:
- Increment failure counter
- Wait 45s (configurable: `draw_retry_delay`)
- Retry up to 3 times (configurable: `max_draw_retries`)
- Continue as long as still in time window

## Error Handling

### EventManager Failure
- MemoryStore data becomes stale
- Operator continues with last known state
- Draw loop keeps checking scheduled draws
- No new events propagated

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
draw_check_interval: float = 10.0      # How often to check for scheduled draws
draw_retry_delay: float = 45.0         # Seconds to wait before retry
max_draw_retries: int = 3              # Maximum retry attempts
tx_timeout_seconds: int = 180          # Transaction confirmation timeout
```

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