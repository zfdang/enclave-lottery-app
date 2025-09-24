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
    address public immutable publisher;        // Contract deployer, receives commission
    address public sparsity;                   // Cloud manager, manages operator
    address public operator;                   // Round manager, handles lottery rounds
    
    // =============== IMMUTABLE CONFIGURATION ===============
    uint256 public immutable publisherCommissionRate; // Basis points (200 = 2%)
    uint256 public immutable sparsityCommissionRate;  // Basis points (300 = 3%)
    uint256 public minBetAmount;            // Minimum bet in wei (operator can modify in waiting state)
    uint256 public bettingDuration;         // Betting period in seconds
    uint256 public minDrawDelayAfterEnd;    // Minimum delay before operator can draw
    uint256 public maxDrawDelayAfterEnd;    // Maximum delay before anyone can refund
    uint256 public minEndTimeExtension;     // Minimum time extension when operator extends betting
    uint256 public minParticipants;         // Minimum players required (2)
    
    // =============== ENUMS ===============
    enum RoundState { Waiting, Betting, Drawing, Completed, Refunded }
    
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
    
    // =============== STATE VARIABLES ===============
    uint256 public roundId;
    RoundState public state;         // Current overall state
    
    // Current round data (only current round is stored)
    LotteryRound public round;
    mapping(address => uint256) public bets; // player => betAmount for current round
    address[] public participants; // participants array for current round
    
    // =============== EVENTS ===============
    event RoundCreated(
        uint256 indexed roundId,
        uint256 startTime,
        uint256 endTime,
        uint256 minDrawTime,
        uint256 maxDrawTime
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
        uint256 newEndTime
    );
    
    event RoundStateChanged(
        uint256 indexed roundId,
        RoundState oldState,
        RoundState newState
    );
    
    event RoundCompleted(
        uint256 indexed roundId,
        address indexed winner,
        uint256 totalPot,
        uint256 winnerPrize,
        uint256 publisherCommission,
        uint256 sparsityCommission,
        uint256 randomSeed
    );
    
    event RoundRefunded(
        uint256 indexed roundId,
        uint256 totalRefunded,
        uint256 participantCount,
        string reason
    );
    
    event MinBetAmountUpdated(uint256 oldAmount, uint256 newAmount);
    event SparsitySet(address indexed sparsity);
    event OperatorUpdated(address indexed oldOperator, address indexed newOperator);
    
    // =============== MODIFIERS ===============
    modifier onlyPublisher() {
        require(msg.sender == publisher, "Only publisher can call this function");
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
        uint256 _sparsityCommissionRate,
        uint256 _minBetAmount,
        uint256 _bettingDuration,
        uint256 _minDrawDelayAfterEnd,
        uint256 _maxDrawDelayAfterEnd,
        uint256 _minEndTimeExtension,
        uint256 _minParticipants
    ) {
        require(_publisherCommissionRate <= 500, "Publisher commission too high (max 5%)");
        require(_sparsityCommissionRate <= 500, "Sparsity commission too high (max 5%)");
        require(_publisherCommissionRate + _sparsityCommissionRate <= 1000, "Total commission too high (max 10%)");
        require(_minBetAmount > 0, "Min bet amount must be positive");
        require(_bettingDuration > 0, "Betting duration must be positive");
        require(_minDrawDelayAfterEnd >= 60, "Min draw delay must be at least 1 minute");
        require(_maxDrawDelayAfterEnd > _minDrawDelayAfterEnd, "Max draw delay must be greater than min");
        require(_minEndTimeExtension >= 300, "Min end time extension must be at least 5 minutes");
        require(_minParticipants >= 2, "Min participants must be at least 2");
        
        publisher = msg.sender;
        sparsity = address(0);                    // Will be set by publisher
        operator = address(0);                    // Will be set by sparsity
        publisherCommissionRate = _publisherCommissionRate;
        sparsityCommissionRate = _sparsityCommissionRate;
        
        minBetAmount = _minBetAmount;
        bettingDuration = _bettingDuration;
        minDrawDelayAfterEnd = _minDrawDelayAfterEnd;
        maxDrawDelayAfterEnd = _maxDrawDelayAfterEnd;
        minEndTimeExtension = _minEndTimeExtension;
        minParticipants = _minParticipants;
        
        roundId = 0;
        state = RoundState.Waiting;
    }
    
    // =============== PUBLISHER FUNCTIONS ===============
    
    /**
     * @dev Set the sparsity address (one-time only)
     * @param _sparsity The address of the sparsity (cloud manager)
     * @notice Can only be called by publisher, and only once
     */
    function setSparsity(address _sparsity) external onlyPublisher sparsityNotSet {
        require(_sparsity != address(0), "Invalid sparsity address");
        require(_sparsity != publisher, "Sparsity cannot be publisher");
        
        sparsity = _sparsity;
        
        emit SparsitySet(_sparsity);
    }
    
    // =============== SPARSITY FUNCTIONS ===============
    
    /**
     * @dev Update the operator address (same as setOperator, for clarity)
     * @param _operator The new address of the operator
     * @notice Can only be called by sparsity when in waiting state
     */
    function updateOperator(address _operator) external onlySparsity {
        require(_operator != address(0), "Invalid operator address");
        require(_operator != publisher, "Operator cannot be publisher");
        require(_operator != sparsity, "Operator cannot be sparsity");
        require(state == RoundState.Waiting, "Cannot change operator when not in waiting state");
        
        address oldOperator = operator;
        operator = _operator;
        
        emit OperatorUpdated(oldOperator, _operator);
    }
    
    // =============== OPERATOR FUNCTIONS ===============
    
    /**
     * @dev Update minimum bet amount (only in waiting state)
     * @param _newMinBetAmount New minimum bet amount in wei
     */
    function updateMinBetAmount(uint256 _newMinBetAmount) external onlyOperator {
        require(state == RoundState.Waiting, "Can only update min bet amount in waiting state");
        require(_newMinBetAmount > 0, "Min bet amount must be positive");
        
        uint256 oldAmount = minBetAmount;
        minBetAmount = _newMinBetAmount;
        
        emit MinBetAmountUpdated(oldAmount, _newMinBetAmount);
    }
    
    /**
     * @dev Start a new lottery round
     * @notice Can only be called by operator when in waiting state
     */
    function startNewRound() external onlyOperator {
        require(state == RoundState.Waiting, "Must be in waiting state to start new round");
        
        _clearRoundData();
        
        roundId++;
        
        uint256 startTime = block.timestamp;
        uint256 endTime = startTime + bettingDuration;
        uint256 minDrawTime = endTime + minDrawDelayAfterEnd;
        uint256 maxDrawTime = endTime + maxDrawDelayAfterEnd;
        
        round = LotteryRound({
            roundId: roundId,
            startTime: startTime,
            endTime: endTime,
            minDrawTime: minDrawTime,
            maxDrawTime: maxDrawTime,
            totalPot: 0,
            participantCount: 0,
            winner: address(0),
            publisherCommission: 0,
            sparsityCommission: 0,
            winnerPrize: 0,
            state: RoundState.Betting
        });
        
        _changeState(RoundState.Betting);
        
        emit RoundCreated(roundId, startTime, endTime, minDrawTime, maxDrawTime);
    }
    
    /**
     * @dev Extend the end time of the current betting round
     * @param _newEndTime New end time (must be at least current time + minEndTimeExtension)
     */
    function extendBettingTime(uint256 _newEndTime) external onlyOperator {
        require(state == RoundState.Betting, "Must be in betting state");
        require(roundId > 0, "No active round");
        
        require(block.timestamp <= round.endTime, "Betting period already ended");
        require(_newEndTime >= block.timestamp + minEndTimeExtension, "New end time must be at least minEndTimeExtension from now");
        require(_newEndTime > round.endTime, "New end time must be later than current end time");
        
        uint256 oldEndTime = round.endTime;
        round.endTime = _newEndTime;
        round.minDrawTime = _newEndTime + minDrawDelayAfterEnd;
        round.maxDrawTime = _newEndTime + maxDrawDelayAfterEnd;
        
        emit EndTimeExtended(roundId, oldEndTime, _newEndTime);
    }
    
    /**
     * @dev Manually refund current round when draw time expired
     * @notice Can only be called by operator after maxDrawTime
     */
    function refundRound() external onlyOperator {
        require(state == RoundState.Betting, "Round must be in betting state");
        require(block.timestamp > round.maxDrawTime, "Draw time has not expired yet");
        require(round.totalPot > 0, "No funds to refund");
        
        _refundRound("Draw time expired");
    }
    
    /**
     * @dev Draw winner for the current active round
     * @notice Can only be called by operator after minDrawTime. Auto-refunds if insufficient participants.
     */
    function drawWinner() external onlyOperator {
        require(state == RoundState.Betting, "Round must be in betting state");
        require(block.timestamp >= round.minDrawTime, "Min draw time not reached");
        require(block.timestamp <= round.maxDrawTime, "Draw time expired, refund required");
        require(round.totalPot > 0, "No bets placed");
        
        // Change to drawing state
        round.state = RoundState.Drawing;
        _changeState(RoundState.Drawing);
        
        emit RoundStateChanged(roundId, RoundState.Betting, RoundState.Drawing);
        
        // Check minimum participants - auto refund if insufficient
        if (round.participantCount < minParticipants) {
            _refundRound("Insufficient participants");
            return;
        }
        
        // Generate weighted random winner based on bet amounts
        uint256 randomSeed = uint256(keccak256(abi.encodePacked(
            block.timestamp,
            block.prevrandao,
            block.number,
            roundId,
            round.totalPot
        )));
        
        address winner = _selectWeightedWinner(randomSeed);
        
        // Calculate and distribute payouts
        _distributePayout(winner, randomSeed);
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
        uint256 publisherCommission = (round.totalPot * publisherCommissionRate) / 10000;
        uint256 sparsityCommission = (round.totalPot * sparsityCommissionRate) / 10000;
        uint256 prize = round.totalPot - publisherCommission - sparsityCommission;
        
        // Update round state
        round.winner = winner;
        round.publisherCommission = publisherCommission;
        round.sparsityCommission = sparsityCommission;
        round.winnerPrize = prize;
        round.state = RoundState.Completed;
        
        // Emit completion event
        emit RoundCompleted(roundId, winner, round.totalPot, prize, publisherCommission, sparsityCommission, randomSeed);
        emit RoundStateChanged(roundId, RoundState.Drawing, RoundState.Completed);
        
        // Transfer funds
        if (publisherCommission > 0) {
            payable(publisher).transfer(publisherCommission);
        }
        if (sparsityCommission > 0 && sparsity != address(0)) {
            payable(sparsity).transfer(sparsityCommission);
        }
        payable(winner).transfer(prize);
        
        // Clear current round data and set state to waiting for next round
        _clearRoundData();
        _changeState(RoundState.Waiting);
    }
    
    /**
     * @dev Internal function to change global state and emit event
     */
    function _changeState(RoundState newState) internal {
        RoundState oldState = state;
        state = newState;
        
        emit RoundStateChanged(roundId, oldState, newState);
    }
    
    /**
     * @dev Internal function to refund the current round
     * @param reason Reason for refund
     */
    function _refundRound(string memory reason) internal {
        round.state = RoundState.Refunded;
        
        uint256 totalRefunded = _refundParticipants();
        
        emit RoundRefunded(roundId, totalRefunded, round.participantCount, reason);
        emit RoundStateChanged(roundId, RoundState.Drawing, RoundState.Refunded);
        
        // Clear current round data and set state to waiting for next round
        _clearRoundData();
        _changeState(RoundState.Waiting);
    }
    
    // =============== PLAYER FUNCTIONS ===============
    
    /**
     * @dev Place a bet in the current active round
     * @notice Players can place multiple bets, minimum bet amount required
     */
    function placeBet() external payable nonReentrant {
        require(state == RoundState.Betting || state == RoundState.Waiting, "Invalid state for betting");
        require(msg.value >= minBetAmount, "Bet amount too low");
        
        // If in waiting state, automatically start new round
        if (state == RoundState.Waiting) {
            _startNewRoundFromFirstBet();
        }
        
        require(block.timestamp >= round.startTime, "Betting not started");
        require(block.timestamp <= round.endTime, "Betting period ended");
        require(round.state == RoundState.Betting, "Round not in betting state");
        
        // Add to participant list if first bet
        if (bets[msg.sender] == 0) {
            participants.push(msg.sender);
            round.participantCount++;
        }
        
        // Update bet amount and total pot
        bets[msg.sender] += msg.value;
        round.totalPot += msg.value;
        
        emit BetPlaced(roundId, msg.sender, msg.value, round.totalPot, block.timestamp);
    }
    
    /**
     * @dev Internal function to start a new round when first bet is placed
     */
    function _startNewRoundFromFirstBet() internal {
        _clearRoundData();
        
        roundId++;
        
        uint256 startTime = block.timestamp;
        uint256 endTime = startTime + bettingDuration;
        uint256 minDrawTime = endTime + minDrawDelayAfterEnd;
        uint256 maxDrawTime = endTime + maxDrawDelayAfterEnd;
        
        round = LotteryRound({
            roundId: roundId,
            startTime: startTime,
            endTime: endTime,
            minDrawTime: minDrawTime,
            maxDrawTime: maxDrawTime,
            totalPot: 0,
            participantCount: 0,
            winner: address(0),
            publisherCommission: 0,
            sparsityCommission: 0,
            winnerPrize: 0,
            state: RoundState.Betting
        });
        
        _changeState(RoundState.Betting);
        
        emit RoundCreated(roundId, startTime, endTime, minDrawTime, maxDrawTime);
    }
    
    // =============== PUBLIC FUNCTIONS ===============
    
    /**
     * @dev Refund current round if it has expired (public function - anyone can call)
     * @notice Anyone can call this if maxDrawTime has passed without completion
     */
    function refundExpiredRound() external {
        require(roundId > 0, "No active round");
        require(round.state == RoundState.Betting, "Round not in betting state");
        require(block.timestamp > round.maxDrawTime, "Max draw time not expired");
        
        _refundRound("Draw time expired - public refund");
    }
    
    // =============== INTERNAL FUNCTIONS ===============
    
    /**
     * @dev Internal function to clear current round data for new round
     */
    function _clearRoundData() internal {
        // Clear current round bets mapping for previous participants
        for (uint256 i = 0; i < participants.length; i++) {
            delete bets[participants[i]];
        }
        
        // Clear current round participants array
        delete participants;
    }
    
    /**
     * @dev Internal function to refund all participants of current round
     * @return totalRefunded Total amount refunded
     */
    function _refundParticipants() internal returns (uint256 totalRefunded) {
        for (uint256 i = 0; i < participants.length; i++) {
            address participant = participants[i];
            uint256 betAmount = bets[participant];
            
            if (betAmount > 0) {
                bets[participant] = 0; // Prevent re-entrancy
                payable(participant).transfer(betAmount);
                totalRefunded += betAmount;
            }
        }
        
        return totalRefunded;
    }
    

    
    // =============== VIEW FUNCTIONS ===============
    
    /**
     * @dev Get current round information
     */
    function getRound() external view returns (LotteryRound memory) {
        return round;
    }
    
    /**
     * @dev Get current state
     */
    function getState() external view returns (RoundState) {
        return state;
    }
    
    /**
     * @dev Get current round participants
     */
    function getParticipants() external view returns (address[] memory) {
        return participants;
    }
    
    /**
     * @dev Get player's bet amount for current round
     * @param player The player's address
     */
    function getPlayerBet(address player) external view returns (uint256) {
        return bets[player];
    }
    

    /**
     * @dev Check if current round can be drawn
     */
    function canDraw() external view returns (bool) {
        if (state != RoundState.Betting || roundId == 0) return false;
        
        return (
            round.state == RoundState.Betting &&
            block.timestamp >= round.minDrawTime &&
            block.timestamp <= round.maxDrawTime &&
            round.totalPot > 0
        );
    }
    
    /**
     * @dev Check if current round can be refunded
     */
    function canRefund() external view returns (bool) {
        if (state != RoundState.Betting || roundId == 0) return false;
        
        return (
            round.state == RoundState.Betting &&
            block.timestamp > round.maxDrawTime
        );
    }
    
    /**
     * @dev Get current round timing information
     */
    function getRoundTiming() external view returns (
        uint256 startTime,
        uint256 endTime,
        uint256 minDrawTime,
        uint256 maxDrawTime,
        uint256 currentTime
    ) {
        if (state != RoundState.Waiting && roundId > 0) {
            return (round.startTime, round.endTime, round.minDrawTime, round.maxDrawTime, block.timestamp);
        }
        return (0, 0, 0, 0, block.timestamp);
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
        uint256 minPart,
        bool sparsityIsSet
    ) {
        return (
            publisher,
            sparsity,
            operator,
            publisherCommissionRate,
            sparsityCommissionRate,
            minBetAmount,
            bettingDuration,
            minDrawDelayAfterEnd,
            maxDrawDelayAfterEnd,
            minEndTimeExtension,
            minParticipants,
            sparsity != address(0)
        );
    }
}
