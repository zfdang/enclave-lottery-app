// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title Lottery Contract - 4-Role Architecture
 * @dev Smart contract for managing lottery rounds with publisher/sparsity/operator/player roles
 * @notice Publisher deploys, Sparsity manages operator, Operator runs rounds, Players place bets
 */
contract Lottery {
    // =============== REENTRANCY GUARD ===============
    bool private _locked;
    
    modifier nonReentrant() {
        require(!_locked, "ReentrancyGuard: reentrant call");
        _locked = true;
        _;
        _locked = false;
    }
    
    // =============== ROLES ===============
    address public immutable PUBLISHER;        // Contract deployer, receives commission
    address public sparsity;                   // Cloud manager, manages operator
    address public operator;                   // Round manager, handles lottery rounds
    
    // =============== IMMUTABLE CONFIGURATION BY PUBLISHER ===============
    uint256 public immutable PUBLISHER_COMMISSION_RATE; // Basis points (200 = 2%)
    uint256 public immutable SPARSITY_COMMISSION_RATE;  // Basis points (300 = 3%)
    
    // =============== CONFIGURATION BY OPERATOR ===============
    uint256 public minBetAmount;            // Minimum bet in wei (operator can modify in waiting state)
    uint256 public bettingDuration;         // Betting period in seconds
    uint256 public minDrawDelayAfterEnd;    // Minimum delay before operator can draw
    uint256 public maxDrawDelayAfterEnd;    // Maximum delay before anyone can refund
    uint256 public minEndTimeExtension;     // Minimum time extension when operator extends betting
    uint256 public minParticipants;         // Minimum players required (2)
    
    // =============== ENUMS ===============
    enum RoundState { WAITING, BETTING, DRAWING, COMPLETED, REFUNDED }
    
    // =============== STRUCTS ===============
    struct LotteryRound {
        uint256 roundId;
        uint256 startTime;
        uint256 endTime;
        uint256 minDrawTime;        // endTime + minDrawDelayAfterEnd
        uint256 maxDrawTime;        // endTime + maxDrawDelayAfterEnd
        uint256 totalPot;
        uint256 participantCount;
        address winner;
        uint256 publisherCommission;
        uint256 sparsityCommission;
        uint256 winnerPrize;
        RoundState state;
    }
    
    // Current round data 
    LotteryRound public round;
    mapping(address => uint256) public bets; // player => betAmount for current round
    address[] public participants; // participants array for current round
    // Pull-payment balances for addresses (publisher, sparsity, etc.)
    mapping(address => uint256) public pendingWithdrawals;
    
    // =============== EVENTS ===============
    event RoundCreated(
        uint256 indexed roundId,
        uint256 startTime,
        uint256 endTime,
        uint256 minDrawTime,
        uint256 maxDrawTime,
        uint256 timestamp
    );

    event BetPlaced(
        uint256 indexed roundId,
        address indexed player,
        uint256 amount,
        uint256 newTotal,
        uint256 timestamp
    );

    event EndTimeExtended(
        uint256 indexed roundId,
        uint256 oldEndTime,
        uint256 newEndTime,
        uint256 timestamp
    );

    event RoundStateChanged(
        uint256 indexed roundId,
        RoundState oldState,
        RoundState newState,
        uint256 timestamp
    );

    event RoundCompleted(
        uint256 indexed roundId,
        address indexed winner,
        uint256 totalPot,
        uint256 winnerPrize,
        uint256 publisherCommission,
        uint256 sparsityCommission,
        uint256 randomSeed,
        uint256 timestamp
    );

    event RoundRefunded(
        uint256 indexed roundId,
        uint256 totalRefunded,
        uint256 participantCount,
        string reason,
        uint256 timestamp
    );

    event MinBetAmountUpdated(uint256 oldAmount, uint256 newAmount, uint256 timestamp);
    event BettingDurationUpdated(uint256 oldDuration, uint256 newDuration, uint256 timestamp);
    event MinParticipantsUpdated(uint256 oldMin, uint256 newMin, uint256 timestamp);
    event SparsitySet(address indexed sparsity, uint256 timestamp);
    event OperatorUpdated(address indexed oldOperator, address indexed newOperator, uint256 timestamp);
    event Withdrawn(address indexed to, uint256 amount, uint256 timestamp);
    
    // =============== MODIFIERS ===============
    modifier onlyPublisher() {
        require(msg.sender == PUBLISHER, "Only publisher can call this function");
        _;
    }
    
    modifier onlySparsity() {
        require(sparsity != address(0), "Sparsity not set");
        require(msg.sender == sparsity, "Only sparsity can call this function");
        _;
    }
    
    modifier onlyOperator() {
        require(operator != address(0), "Operator not set");
        require(msg.sender == operator, "Only operator can call this function");
        _;
    }
    
    modifier sparsityNotSet() {
        require(sparsity == address(0), "Sparsity already set");
        _;
    }
    
    
    // =============== CONSTRUCTOR ===============
    constructor(
        uint256 _publisherCommissionRate,
        uint256 _sparsityCommissionRate
    ) {
        require(_publisherCommissionRate <= 500, "Publisher commission too high (max 5%)");
        require(_sparsityCommissionRate <= 500, "Sparsity commission too high (max 5%)");
        require(_publisherCommissionRate + _sparsityCommissionRate <= 1000, "Total commission too high (max 10%)");

        PUBLISHER = msg.sender;
        sparsity = address(0);                    // Will be set by publisher
        operator = address(0);                    // Will be set by sparsity
        PUBLISHER_COMMISSION_RATE = _publisherCommissionRate;
        SPARSITY_COMMISSION_RATE = _sparsityCommissionRate;

        // Set sensible defaults for other config values
        minBetAmount = 0.001 ether;
        bettingDuration = 120 seconds;
        minDrawDelayAfterEnd = 30 seconds;
        maxDrawDelayAfterEnd = 120 seconds;
        minEndTimeExtension = 120 seconds;
        minParticipants = 2;

        // start with roundId = 1 and WAITING state
        round = LotteryRound({
            roundId: 1,
            startTime: 0,
            endTime: 0,
            minDrawTime: 0,
            maxDrawTime: 0,
            totalPot: 0,
            participantCount: 0,
            winner: address(0),
            publisherCommission: 0,
            sparsityCommission: 0,
            winnerPrize: 0,
            state: RoundState.WAITING
        });
    }

    // =============== PUBLISHER FUNCTIONS ===============
    
    /**
     * @dev Set the sparsity address (one-time only)
     * @param _sparsity The address of the sparsity (cloud manager)
     * @notice Can only be called by publisher, and only once
     */
    function setSparsity(address _sparsity) external onlyPublisher sparsityNotSet {
        require(_sparsity != address(0), "Invalid sparsity address");
        require(_sparsity != PUBLISHER, "Sparsity cannot be publisher");
        
        sparsity = _sparsity;
        emit SparsitySet(_sparsity, block.timestamp);
    }
    
    // =============== SPARSITY FUNCTIONS ===============
    
    /**
     * @dev Update the operator address (same as setOperator, for clarity)
     * @param _operator The new address of the operator
     * @notice Can only be called by sparsity when in waiting state
     */
    function updateOperator(address _operator) external onlySparsity {
        require(_operator != address(0), "Invalid operator address");
        require(_operator != PUBLISHER, "Operator cannot be publisher");
        require(_operator != sparsity, "Operator cannot be sparsity");
        require(round.state == RoundState.WAITING, "Cannot change operator when not in waiting state");

        address oldOperator = operator;
        operator = _operator;
        emit OperatorUpdated(oldOperator, _operator, block.timestamp);
    }
    
    // =============== OPERATOR FUNCTIONS ===============
    
    /**
     * @dev Update minimum bet amount (only in waiting state)
     * @param _newMinBetAmount New minimum bet amount in wei
     */
    function updateMinBetAmount(uint256 _newMinBetAmount) external onlyOperator {
        require(round.state == RoundState.WAITING, "Can only update min bet amount in waiting state");
        require(_newMinBetAmount > 0, "Min bet amount must be positive");
        
        uint256 oldAmount = minBetAmount;
        minBetAmount = _newMinBetAmount;
        emit MinBetAmountUpdated(oldAmount, _newMinBetAmount, block.timestamp);
    }

    /**
     * @dev Return the configured minimum bet amount (in wei)
     */
    function getMinBetAmount() external view returns (uint256) {
        return minBetAmount;
    }

    /**
     * @dev Update the betting duration (only in waiting state)
     * @param _newDuration New betting duration in seconds
     */
    function updateBettingDuration(uint256 _newDuration) external onlyOperator {
        require(round.state == RoundState.WAITING, "Can only update betting duration in waiting state");
        require(_newDuration > 0, "Betting duration must be positive");

        uint256 oldDuration = bettingDuration;
        bettingDuration = _newDuration;
        emit BettingDurationUpdated(oldDuration, _newDuration, block.timestamp);
    }

    /**
     * @dev Update the minimum number of participants required (only in waiting state)
     * @param _newMinParticipants New minimum participants (must be >= 2)
     */
    function updateMinParticipants(uint256 _newMinParticipants) external onlyOperator {
        require(round.state == RoundState.WAITING, "Can only update min participants in waiting state");
        require(_newMinParticipants >= 2, "Minimum participants must be at least 2");

        uint256 oldMin = minParticipants;
        minParticipants = _newMinParticipants;
        emit MinParticipantsUpdated(oldMin, _newMinParticipants, block.timestamp);
    }
    
    /**
     * @dev Start a new lottery round
     * @notice Can only be called by operator when in waiting state
     */
    function startRound() external onlyOperator {
        require(round.state == RoundState.WAITING, "Must be in waiting state to start new round");
        _startRoundFromWaiting();
    }
    
    /**
     * @dev Extend the end time of the current betting round
     * @param _newEndTime New end time (must be at least current time + minEndTimeExtension)
     */
    function extendBettingTime(uint256 _newEndTime) external onlyOperator {
        require(round.state == RoundState.BETTING, "Must be in betting state");
        require(round.roundId > 0, "No active round");

        require(block.timestamp <= round.endTime, "Betting period already ended");
        require(_newEndTime >= block.timestamp + minEndTimeExtension, "New end time must be at least minEndTimeExtension from now");
        require(_newEndTime > round.endTime, "New end time must be later than current end time");

        uint256 oldEndTime = round.endTime;
        round.endTime = _newEndTime;
        round.minDrawTime = _newEndTime + minDrawDelayAfterEnd;
        round.maxDrawTime = _newEndTime + maxDrawDelayAfterEnd;
        emit EndTimeExtended(round.roundId, oldEndTime, _newEndTime, block.timestamp);
    }
    
    /**
     * @dev Refund current round, initiated by operator
     */
    function refundRound() external onlyOperator {
        require(round.state == RoundState.BETTING, "Round must be in betting state");
        require(round.totalPot > 0, "No funds to refund");

        _refundRound("Operator-initiated refund");

        // start new round in waiting state, waiting for first bet or operator to start it explicitly
        _createNewRoundToWaiting();
    }
    
    /**
     * @dev Draw winner for the current active round
     * @notice Can only be called by operator after minDrawTime. Auto-refunds if insufficient participants.
     */
    function drawWinner() external onlyOperator {
        require(round.state == RoundState.BETTING, "Round must be in betting state");
        require(block.timestamp >= round.minDrawTime, "Min draw time not reached");
        require(block.timestamp <= round.maxDrawTime, "Draw time expired, refund required");
        require(round.totalPot > 0, "No bets placed");
        
        // Change to drawing state
        round.state = RoundState.DRAWING;
        _changeState(RoundState.DRAWING);
        
        // Check minimum participants - auto refund if insufficient
        if (round.participantCount < minParticipants) {
            _refundRound("Insufficient participants");
        } else {
            // Generate weighted random winner based on bet amounts
            uint256 randomSeed = uint256(keccak256(abi.encodePacked(
                block.timestamp,
                block.prevrandao,
                block.number,
                round.roundId,
                round.totalPot
            )));
            
            address winner = _selectWeightedWinner(randomSeed);
            
            // Calculate and distribute payouts
            _distributePayout(winner, randomSeed);
        }
        
        // create new round in waiting state, waiting for first bet or operator to start it explicitly
        _createNewRoundToWaiting();
    }
    
    /**
     * @dev Internal function to select winner based on weighted probability (proportional to bet amounts)
     * @param randomSeed Random seed for selection
     * @return winner The selected winner address
     */
    function _selectWeightedWinner(uint256 randomSeed) internal view returns (address) {
        uint256 randomValue = randomSeed % round.totalPot;
        uint256 cumulativeSum = 0;
        
        for (uint256 i = 0; i < participants.length; i++) {
            address participant = participants[i];
            uint256 betAmount = bets[participant];
            cumulativeSum += betAmount;
            
            if (randomValue < cumulativeSum) {
                return participant;
            }
        }
        
        // Fallback to last participant (should not happen with proper implementation)
        return participants[participants.length - 1];
    }
    
    /**
     * @dev Internal function to calculate and distribute payouts
     */
    function _distributePayout(address winner, uint256 randomSeed) internal {
        // Calculate commissions
        uint256 publisherCommission = (round.totalPot * PUBLISHER_COMMISSION_RATE) / 10000;
        uint256 sparsityCommission = (round.totalPot * SPARSITY_COMMISSION_RATE) / 10000;
        uint256 prize = round.totalPot - publisherCommission - sparsityCommission;
        
        // Update round state
        round.winner = winner;
        round.publisherCommission = publisherCommission;
        round.sparsityCommission = sparsityCommission;
        round.winnerPrize = prize;
        
        // Emit completion event
        emit RoundCompleted(round.roundId, winner, round.totalPot, prize, publisherCommission, sparsityCommission, randomSeed, block.timestamp);
        _changeState(RoundState.COMPLETED);
        
        // Credit publisher and sparsity commissions to pending withdrawals (pull-payment)
        if (publisherCommission > 0) {
            pendingWithdrawals[PUBLISHER] += publisherCommission;
        }
        if (sparsityCommission > 0 && sparsity != address(0)) {
            pendingWithdrawals[sparsity] += sparsityCommission;
        }

        // Transfer prize to winner immediately (keep existing behavior)
        payable(winner).transfer(prize);
    }
    
    /**
     * @dev Internal function to change global state and emit event
     */
    function _changeState(RoundState newState) internal {
        RoundState oldState = round.state;
        round.state = newState;
        emit RoundStateChanged(round.roundId, oldState, newState, block.timestamp);
    }
    
    /**
     * @dev Internal function to refund the current round
     * @param reason Reason for refund
     */
    function _refundRound(string memory reason) internal {
        uint256 totalRefunded = 0;
        for (uint256 i = 0; i < participants.length; i++) {
            address participant = participants[i];
            uint256 betAmount = bets[participant];
            
            if (betAmount > 0) {
                bets[participant] = 0; // Prevent re-entrancy
                payable(participant).transfer(betAmount);
                totalRefunded += betAmount;
            }
        }
                
        emit RoundRefunded(round.roundId, totalRefunded, round.participantCount, reason, block.timestamp);
        _changeState(RoundState.REFUNDED);
    }
    
    // =============== PLAYER FUNCTIONS ===============
    
    /**
     * @dev Place a bet in the current active round
     * @notice Players can place multiple bets, minimum bet amount required
     */
    function placeBet() external payable nonReentrant {
        // Validate bet amount first
        require(msg.value >= minBetAmount, "Bet amount too low");

        // If currently waiting, implicitly start a new round from this first bet
        if (round.state == RoundState.WAITING) {
            _startRoundFromWaiting();
        }

        // After ensuring a round exists, require that we're within the active betting window
        require(round.state == RoundState.BETTING, "Round not in betting state");
        require(block.timestamp >= round.startTime && block.timestamp <= round.endTime, "Betting not active");
            
        // Add to participant list if first bet
        if (bets[msg.sender] == 0) {
            participants.push(msg.sender);
            round.participantCount++;
        }
        
        // Update bet amount and total pot
        bets[msg.sender] += msg.value;
        round.totalPot += msg.value;
        emit BetPlaced(round.roundId, msg.sender, msg.value, round.totalPot, block.timestamp);
    }
    
    /**
     * @dev Internal function to start the current round when first bet is placed, or started by operator manually
     */
    function _startRoundFromWaiting() internal {
                
        round.startTime = block.timestamp;
        round.endTime = round.startTime + bettingDuration;
        round.minDrawTime = round.endTime + minDrawDelayAfterEnd;
        round.maxDrawTime = round.endTime + maxDrawDelayAfterEnd;
        
        _changeState(RoundState.BETTING);
    }
    
    // =============== PUBLIC FUNCTIONS ===============
    
    /**
     * @dev Refund current round if it has expired (public function - anyone can call)
     * @notice Anyone can call this if maxDrawTime has passed without completion
     */
    function refundExpiredRound() external {
        require(round.state == RoundState.BETTING, "Round not in betting state");
        require(round.participantCount > 0, "No participants in round");
        require(block.timestamp > round.maxDrawTime, "Max draw time not expired");
        
        _refundRound("Draw time expired - public refund");

        // create new round in waiting state, waiting for first bet or operator to start it explicitly
        _createNewRoundToWaiting();
    }
    
    // =============== INTERNAL FUNCTIONS ===============
    
    /**
     * @dev Internal function to reset round to waiting state
     */
    function _createNewRoundToWaiting() internal {
        // check state is completed or refunded
        require(round.state == RoundState.COMPLETED || round.state == RoundState.REFUNDED, "Can only reset from completed or refunded state");
        
        // Clear current round bets mapping for previous participants
        for (uint256 i = 0; i < participants.length; i++) {
            delete bets[participants[i]];
        }
        
        // Clear current round participants array
        delete participants;

        uint256 newRoundId = round.roundId + 1;
        round = LotteryRound({
            roundId: newRoundId,
            startTime: 0,
            endTime: 0,
            minDrawTime: 0,
            maxDrawTime: 0,
            totalPot: 0,
            participantCount: 0,
            winner: address(0),
            publisherCommission: 0,
            sparsityCommission: 0,
            winnerPrize: 0,
            state: RoundState.WAITING
        });

        emit RoundCreated(newRoundId, 0, 0, 0, 0, block.timestamp);
        _changeState(RoundState.WAITING);
    }
    
    // =============== VIEW FUNCTIONS ===============
    
    /**
     * @dev Get current round information
     */
    function getRound() external view returns (LotteryRound memory) {
        return round;
    }
    
    /**
     * @dev Get current round participants
     */
    function getParticipants() external view returns (address[] memory) {
        return participants;
    }

    /**
     * @dev Withdraw pending balance (pull-payment)
     */
    function withdraw() external nonReentrant {
        uint256 amount = pendingWithdrawals[msg.sender];
        require(amount > 0, "No funds available");
        pendingWithdrawals[msg.sender] = 0;
        (bool ok, ) = payable(msg.sender).call{value: amount}("");
        require(ok, "Withdraw failed");
        emit Withdrawn(msg.sender, amount, block.timestamp);
    }

    /**
     * @dev Get bet amount for a specific player in the current round
     */
    function getBetAmount(address player) external view returns (uint256) {
        return bets[player];
    }



    /**
     * @dev Get contract configuration
     */
    function getConfig() external view returns (
        address publisherAddr,
        address sparsityAddr,
        address operatorAddr,
        uint256 publisherCommission,
        uint256 sparsityCommission,
        uint256 minBet,
        uint256 bettingDur,
        uint256 minDrawDelay,
        uint256 maxDrawDelay,
        uint256 minEndTimeExt,
        uint256 minPart
    ) {
        return (
            PUBLISHER,
            sparsity,
            operator,
            PUBLISHER_COMMISSION_RATE,
            SPARSITY_COMMISSION_RATE,
            minBetAmount,
            bettingDuration,
            minDrawDelayAfterEnd,
            maxDrawDelayAfterEnd,
            minEndTimeExtension,
            minParticipants
        );
    }
}
