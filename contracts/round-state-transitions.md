# Round State Transitions Documentation

## Overview

The lottery contract uses a `RoundState` enum to track the lifecycle of each lottery round:

```solidity
enum RoundState { WAITING, BETTING, DRAWING, COMPLETED, REFUNDED }
```

## State Transition Diagram

```
WAITING → BETTING → DRAWING → COMPLETED
    ↑         ↓         ↓         ↓
    └─────────┴─────────┴─────────┘
              ↓
           REFUNDED
              ↓
           WAITING
```

## Detailed State Transitions

### 1. WAITING → BETTING

**Triggering Functions:**
- `startNewRound()` - Operator explicitly starts a new round
- `placeBet()` - First bet implicitly starts a new round (via `_startNewRoundFromFirstBet()`)

**Conditions:**
- Current state must be `WAITING`
- For `startNewRound()`: Must be called by operator
- For `placeBet()`: Any player can trigger with valid bet amount

**Implementation:**
```solidity
// In startNewRound() and _startNewRoundFromFirstBet()
round.state = RoundState.BETTING;
_changeState(RoundState.BETTING);
```

### 2. BETTING → DRAWING

**Triggering Function:**
- `drawWinner()` - Operator initiates the drawing process

**Conditions:**
- Current state must be `BETTING`
- Must be called by operator
- `block.timestamp >= round.minDrawTime` (minimum draw delay has passed)
- `block.timestamp <= round.maxDrawTime` (draw time not expired)
- `round.totalPot > 0` (has bets to draw from)

**Implementation:**
```solidity
round.state = RoundState.DRAWING;
_changeState(RoundState.DRAWING);
```

### 3. DRAWING → COMPLETED

**Triggering Function:**
- `_distributePayout()` - Internal function called after successful winner selection

**Conditions:**
- Current state must be `DRAWING`
- `round.participantCount >= minParticipants` (sufficient participants)
- Winner successfully selected and payouts calculated

**Implementation:**
```solidity
round.state = RoundState.COMPLETED;
emit RoundCompleted(...);
emit RoundStateChanged(round.roundId, RoundState.DRAWING, RoundState.COMPLETED);
```

### 4. BETTING → REFUNDED

**Triggering Functions:**
- `refundRound()` - Operator-initiated refund
- `refundExpiredRound()` - Public refund after max draw time
- `drawWinner()` - Auto-refund when insufficient participants

**Conditions:**

**For `refundRound()` (Operator):**
- Current state must be `BETTING`
- Must be called by operator
- `round.totalPot > 0`
- Can be called anytime during BETTING phase

**For `refundExpiredRound()` (Public):**
- Current state must be `BETTING`
- `round.roundId > 0` (active round exists)
- `block.timestamp > round.maxDrawTime` (draw time expired)
- Anyone can call

**For auto-refund in `drawWinner()`:**
- Current state becomes `DRAWING` first
- `round.participantCount < minParticipants`

**Implementation:**
```solidity
round.state = RoundState.REFUNDED;
emit RoundRefunded(...);
emit RoundStateChanged(round.roundId, RoundState.DRAWING, RoundState.REFUNDED);
```

### 5. COMPLETED/REFUNDED → WAITING

**Triggering Function:**
- `_startNewRoundInWaiting()` - Internal function to reset for next round

**Conditions:**
- Current state must be `COMPLETED` or `REFUNDED`
- Called automatically after round completion or refund

**Implementation:**
```solidity
round.state = RoundState.WAITING;
_changeState(RoundState.WAITING);
```

## Function-by-Function State Changes

### Public/External Functions

| Function | From State | To State | Who Can Call | Conditions |
|----------|------------|----------|--------------|------------|
| `startNewRound()` | WAITING | BETTING | Operator | Must be in waiting state |
| `placeBet()` | WAITING | BETTING | Anyone | First bet triggers implicit start |
| `drawWinner()` | BETTING | DRAWING | Operator | Within draw time window, has bets |
| `refundRound()` | BETTING | REFUNDED | Operator | Anytime during betting, has funds |
| `refundExpiredRound()` | BETTING | REFUNDED | Anyone | After max draw time expired |

### Internal Functions

| Function | From State | To State | Trigger |
|----------|------------|----------|---------|
| `_startNewRoundFromFirstBet()` | WAITING | BETTING | First `placeBet()` call |
| `_distributePayout()` | DRAWING | COMPLETED | Successful winner selection |
| `_refundRound()` | BETTING/DRAWING | REFUNDED | Various refund scenarios |
| `_startNewRoundInWaiting()` | COMPLETED/REFUNDED | WAITING | After round ends |

## Time-Based Constraints

### Timing Windows
- **Betting Period**: `round.startTime` to `round.endTime`
- **Draw Window**: `round.minDrawTime` to `round.maxDrawTime`
- **Public Refund**: After `round.maxDrawTime`

### Key Timestamps
```solidity
startTime = block.timestamp
endTime = startTime + bettingDuration
minDrawTime = endTime + minDrawDelayAfterEnd  
maxDrawTime = endTime + maxDrawDelayAfterEnd
```

## State Validation Rules

### Current State Checks
- Most functions validate current state with `require(round.state == RoundState.X)`
- State transitions are strictly enforced
- No direct state jumps (e.g., WAITING → COMPLETED)

### Round ID Validation
- New rounds increment `round.roundId`
- Round ID 0 indicates no active round (initial WAITING state)
- Functions check `round.roundId > 0` for active round validation

## Events Emitted

All state transitions emit `RoundStateChanged` event:
```solidity
event RoundStateChanged(
    uint256 indexed roundId,
    RoundState oldState,
    RoundState newState
);
```

Additional events for specific transitions:
- `RoundCreated` - WAITING → BETTING
- `RoundCompleted` - DRAWING → COMPLETED  
- `RoundRefunded` - BETTING/DRAWING → REFUNDED

## Error Conditions

### Common Validation Failures
- Wrong state for function call
- Insufficient permissions (not operator)
- Time constraints violated
- No funds to process
- No active round when required

### Example Error Messages
```solidity
"Must be in waiting state to start new round"
"Round must be in betting state"  
"Min draw time not reached"
"Draw time expired, refund required"
"No funds to refund"
```