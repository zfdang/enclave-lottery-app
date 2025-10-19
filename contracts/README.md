# Smart Contracts

This directory contains the smart contracts for the Enclave Lottery App with 4-role architecture and optimized storage.

## Files

- **`Lottery.sol`** - Main lottery contract with 4-role architecture and current-round-only storage
- **`compiled/`** - Compiled contract artifacts (auto-generated)

## Contract Architecture

The lottery contract implements a 4-role system with gas-optimized storage:

- **Publisher**: Deploys contracts, receives commission (configurable), sets sparsity (one-time)
- **Sparsity**: Manages operator nodes in cloud, receives commission (configurable)
- **Operator**: Manages lottery rounds (start/draw), operational role only
- **Players**: Place bets and participate in draws, receive winnings

### Storage Optimization (v2.0)

The contract now uses **current-round-only storage** for gas efficiency:

- **Current Round Data**: Stored in contract state for active operations
- **Historical Data**: Available only through blockchain events
- **Gas Savings**: Significant reduction in storage costs by eliminating historical mappings

#### Storage Structure
```solidity
// Current Round Storage
LotteryRound public currentRound;           // Single active round
mapping(address => uint256) public currentRoundBets;  // Current round bets
address[] public currentRoundParticipants;  // Current round participants

// Historical Data: Events Only
event RoundCompleted(...);  // Winner and payout info
event BetPlaced(...);       // Individual bet records
event RoundRefunded(...);   // Refund information
```

## Game Flow & States

The contract implements a 5-state lottery system:

1. **Waiting**: No active round, ready to start new lottery
2. **Betting**: Players can place bets, round is active
3. **Drawing**: Operator drawing winner, no new bets accepted
4. **Completed**: Winner selected, prizes distributed
5. **Refunded**: Round cancelled, participants refunded

### Round Lifecycle
```
Waiting → (startNewRound) → Betting → (drawWinner) → Drawing → Completed → Waiting
                              ↓                                    ↑
                         (conditions not met)                     ↓
                              ↓                              Refunded
                          Refunded ←------------------------←
```

## Key Functions

### Player Functions
- `placeBet()` - Place bet in current active round (payable, no parameters needed)

### Operator Functions  
- `startNewRound()` - Start new lottery round
- `drawWinner()` - Draw winner for current round (after min draw time)
- `refundCurrentRound()` - Manually refund expired round
- `extendBettingTime(uint256)` - Extend current round betting period

### View Functions
- `getCurrentRound()` - Get current round information
- `getCurrentRoundParticipants()` - Get current round participants  
- `getCurrentRoundPlayerBet(address)` - Get player's current round bet
- `canDrawCurrentRound()` - Check if current round can be drawn
- `getConfig()` - Get contract configuration

## Role Flow

```
Publisher → Deploys → Sets Sparsity → Steps Back
Sparsity → Manages Operator → Receives Commission  
Operator → Runs Rounds → Conducts Draws
Players → Place Bets → Receive Winnings
```

## Usage

Contracts are compiled and deployed using the build system:

```bash
# Compile contracts and build Docker image
./scripts/build_docker.sh

# Deploy to blockchain (requires RPC endpoint)
./scripts/deploy_contracts.sh
```

## Development

### Compilation

The build system automatically compiles contracts using:

```bash
# Full build with ABI distribution
./scripts/build_docker.sh

# Manual compilation using solc
cd /path/to/project
solc --bin --abi --optimize -o contracts/compiled contracts/Lottery.sol
```

### ABI Distribution

The build system automatically distributes compiled ABIs to:
- `/enclave/contracts/abi/` - Backend blockchain client
- `/enclave/frontend/public/contracts/abi/` - Frontend application

### Testing

```bash
# Compile and test locally
solc --bin --abi --optimize -o /tmp/test-compile contracts/Lottery.sol

# Check for compilation errors
echo $?  # Should return 0 for success
```

## API Changes (v2.0)

### Breaking Changes
- `placeBet()` no longer takes roundId parameter (works with current round only)
- `drawWinner()` no longer takes roundId parameter (draws current round only)
- Historical round data only available through events, not storage queries

### New Functions
- `getCurrentRoundParticipants()` - Get current round participants
- `getCurrentRoundPlayerBet(address)` - Get player bet in current round  
- `refundCurrentRound()` - Operator function to refund current round
- `refundExpiredRound()` - Public function to refund expired rounds

### Migration Guide
For applications using the previous version:
```solidity
// Before (v1.0)
contract.placeBet(roundId, {value: betAmount});
contract.drawWinner(roundId);

// After (v2.0) 
contract.placeBet({value: betAmount});  // No roundId needed
contract.drawWinner();  // Draws current round
```

## Security Features

- **Role-based Access Control**: Immutable publisher, managed sparsity and operator roles
- **Reentrancy Protection**: Built-in reentrancy guard for all payable functions
- **Cryptographically Secure Randomness**: Uses `block.prevrandao` for winner selection
- **Weighted Selection**: Winner selection proportional to bet amounts
- **Automatic Safeguards**: 
  - Minimum participant requirements
  - Time-based draw windows
  - Automatic refunds for expired rounds
- **Transparent Fund Handling**: All transactions on-chain with event logging

## Gas Optimization Benefits

The v2.0 storage optimization provides:

- **Reduced Deployment Cost**: Smaller contract size without historical storage mappings
- **Lower Transaction Costs**: Current-round-only operations require less gas
- **Efficient Memory Usage**: Single round struct vs. unbounded historical mappings  
- **Event-based History**: Historical data via events is gas-efficient for queries

## Contract Verification

After deployment, contracts can be verified using:

- Block explorers (Etherscan, Polygonscan, etc.)
- Direct blockchain calls to contract methods
- ABI files distributed by build system

## Version History

- **v1.0**: Initial implementation with historical round storage
- **v2.0**: Storage-optimized version with current-round-only storage (current)