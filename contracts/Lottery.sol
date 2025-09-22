// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title Lottery Contract - 4-Role Architecture
 * @dev Smart contract for managing lottery rounds with publisher/sparsity/operator/player roles
 * @notice Publisher deploys, Sparsity manages operator, Operator runs rounds, Players place bets
 */
contract Lottery {
    // =============== ROLES ===============
    address public immutable publisher;        // Contract deployer, receives commission
    address public sparsity;                   // Cloud manager, manages operator
    address public operator;                   // Round manager, handles lottery rounds
    bool public sparsitySet;                   // One-time flag for sparsity assignment
    
    // =============== IMMUTABLE CONFIGURATION ===============
    uint256 public immutable publisherCommissionRate; // Basis points (200 = 2%)
    uint256 public immutable sparsityCommissionRate;  // Basis points (300 = 3%)
    uint256 public immutable minBetAmount;            // Minimum bet in wei
    uint256 public immutable bettingDuration;         // Betting period in seconds
    uint256 public immutable drawDelayAfterEnd;       // Grace period before draw in seconds
    uint256 public immutable minParticipants;         // Minimum players required (2)
    
    // =============== STRUCTS ===============
    struct LotteryRound {
        uint256 roundId;
        uint256 startTime;
        uint256 endTime;
        uint256 drawTime;
        uint256 totalPot;
        uint256 participantCount;
        address winner;
        uint256 publisherCommission;
        uint256 sparsityCommission;
        uint256 winnerPrize;
        bool completed;
        bool cancelled;
        bool refunded;
    }
    
    // =============== STATE VARIABLES ===============
    uint256 public currentRoundId;
    uint256 public totalRounds;
    bool public hasActiveRound;
    
    mapping(uint256 => LotteryRound) public rounds;
    mapping(uint256 => mapping(address => uint256)) public roundBets; // roundId => player => betAmount
    mapping(uint256 => address[]) public roundParticipants; // roundId => participants array
    mapping(uint256 => mapping(address => bool)) public hasParticipated; // roundId => player => participated
    
    // =============== EVENTS ===============
    event RoundCreated(
        uint256 indexed roundId,
        uint256 startTime,
        uint256 endTime,
        uint256 drawTime
    );
    
    event BetPlaced(
        uint256 indexed roundId,
        address indexed player,
        uint256 amount,
        uint256 newTotal,
        uint256 timestamp
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
    
    event RoundCancelled(
        uint256 indexed roundId,
        string reason,
        uint256 totalRefunded
    );
    
    event RoundRefunded(
        uint256 indexed roundId,
        uint256 totalRefunded,
        uint256 participantCount
    );
    
    event SparsitySet(address indexed sparsity);
    event OperatorUpdated(address indexed oldOperator, address indexed newOperator);
    
    // =============== MODIFIERS ===============
    modifier onlyPublisher() {
        require(msg.sender == publisher, "Only publisher can call this function");
        _;
    }
    
    modifier onlySparsity() {
        require(sparsitySet, "Sparsity not set");
        require(msg.sender == sparsity, "Only sparsity can call this function");
        _;
    }
    
    modifier onlyOperator() {
        require(operator != address(0), "Operator not set");
        require(msg.sender == operator, "Only operator can call this function");
        _;
    }
    
    modifier sparsityNotSet() {
        require(!sparsitySet, "Sparsity already set");
        _;
    }
    
    modifier validRound(uint256 roundId) {
        require(roundId > 0 && roundId <= totalRounds, "Invalid round ID");
        _;
    }
    
    modifier roundExists(uint256 roundId) {
        require(rounds[roundId].roundId != 0, "Round does not exist");
        _;
    }
    
    // =============== CONSTRUCTOR ===============
    constructor(
        uint256 _publisherCommissionRate,
        uint256 _sparsityCommissionRate,
        uint256 _minBetAmount,
        uint256 _bettingDuration,
        uint256 _drawDelayAfterEnd
    ) {
        require(_publisherCommissionRate <= 500, "Publisher commission too high (max 5%)");
        require(_sparsityCommissionRate <= 500, "Sparsity commission too high (max 5%)");
        require(_publisherCommissionRate + _sparsityCommissionRate <= 1000, "Total commission too high (max 10%)");
        require(_minBetAmount > 0, "Minimum bet must be positive");
        require(_bettingDuration >= 300, "Betting duration too short (min 5 minutes)");
        require(_drawDelayAfterEnd >= 60, "Draw delay too short (min 1 minute)");
        
        publisher = msg.sender;
        sparsity = address(0);                    // Will be set by publisher
        operator = address(0);                    // Will be set by sparsity
        sparsitySet = false;
        publisherCommissionRate = _publisherCommissionRate;
        sparsityCommissionRate = _sparsityCommissionRate;
        minBetAmount = _minBetAmount;
        bettingDuration = _bettingDuration;
        drawDelayAfterEnd = _drawDelayAfterEnd;
        minParticipants = 2;
        
        currentRoundId = 0;
        totalRounds = 0;
        hasActiveRound = false;
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
        sparsitySet = true;
        
        emit SparsitySet(_sparsity);
    }
    
    // =============== SPARSITY FUNCTIONS ===============
    
    /**
     * @dev Set the operator address
     * @param _operator The address of the operator
     * @notice Can only be called by sparsity when no active round exists
     */
    function setOperator(address _operator) external onlySparsity {
        require(_operator != address(0), "Invalid operator address");
        require(_operator != publisher, "Operator cannot be publisher");
        require(_operator != sparsity, "Operator cannot be sparsity");
        require(!hasActiveRound, "Cannot change operator during active round");
        
        address oldOperator = operator;
        operator = _operator;
        
        emit OperatorUpdated(oldOperator, _operator);
    }
    
    /**
     * @dev Update the operator address (same as setOperator, for clarity)
     * @param _operator The new address of the operator
     * @notice Can only be called by sparsity when no active round exists
     */
    function updateOperator(address _operator) external onlySparsity {
        require(_operator != address(0), "Invalid operator address");
        require(_operator != publisher, "Operator cannot be publisher");
        require(_operator != sparsity, "Operator cannot be sparsity");
        require(!hasActiveRound, "Cannot change operator during active round");
        
        address oldOperator = operator;
        operator = _operator;
        
        emit OperatorUpdated(oldOperator, _operator);
    }
    
    // =============== OPERATOR FUNCTIONS ===============
    
    /**
     * @dev Start a new lottery round
     * @notice Can only be called by operator when no active round exists
     */
    function startNewRound() external onlyOperator {
        require(!hasActiveRound, "Active round already exists");
        
        totalRounds++;
        currentRoundId = totalRounds;
        
        uint256 startTime = block.timestamp;
        uint256 endTime = startTime + bettingDuration;
        uint256 drawTime = endTime + drawDelayAfterEnd;
        
        rounds[currentRoundId] = LotteryRound({
            roundId: currentRoundId,
            startTime: startTime,
            endTime: endTime,
            drawTime: drawTime,
            totalPot: 0,
            participantCount: 0,
            winner: address(0),
            publisherCommission: 0,
            sparsityCommission: 0,
            winnerPrize: 0,
            completed: false,
            cancelled: false,
            refunded: false
        });
        
        hasActiveRound = true;
        
        emit RoundCreated(currentRoundId, startTime, endTime, drawTime);
    }
    
    /**
     * @dev Draw winner for a completed round
     * @param roundId The ID of the round to draw winner for
     * @notice Can only be called by operator after draw time and with minimum participants
     */
    function drawWinner(uint256 roundId) external onlyOperator validRound(roundId) roundExists(roundId) {
        LotteryRound storage round = rounds[roundId];
        
        require(!round.completed, "Round already completed");
        require(!round.cancelled, "Round was cancelled");
        require(block.timestamp >= round.drawTime, "Draw time not reached");
        require(round.participantCount >= minParticipants, "Not enough participants");
        require(round.totalPot > 0, "No bets placed");
        
        // Generate pseudo-random winner using block-based randomness
        uint256 randomSeed = uint256(keccak256(abi.encodePacked(
            block.timestamp,
            block.prevrandao,
            block.number,
            roundId,
            round.totalPot
        )));
        
        uint256 winnerIndex = randomSeed % round.participantCount;
        address winner = roundParticipants[roundId][winnerIndex];
        
        // Calculate and distribute payouts
        _distributePayout(round, winner, randomSeed);
    }
    
    /**
     * @dev Internal function to calculate and distribute payouts
     */
    function _distributePayout(LotteryRound storage round, address winner, uint256 randomSeed) internal {
        // Calculate commissions
        uint256 publisherCommission = (round.totalPot * publisherCommissionRate) / 10000;
        uint256 sparsityCommission = (round.totalPot * sparsityCommissionRate) / 10000;
        uint256 prize = round.totalPot - publisherCommission - sparsityCommission;
        
        // Update round state
        round.winner = winner;
        round.publisherCommission = publisherCommission;
        round.sparsityCommission = sparsityCommission;
        round.winnerPrize = prize;
        round.completed = true;
        hasActiveRound = false;
        
        // Transfer funds
        if (publisherCommission > 0) {
            payable(publisher).transfer(publisherCommission);
        }
        if (sparsityCommission > 0 && sparsity != address(0)) {
            payable(sparsity).transfer(sparsityCommission);
        }
        payable(winner).transfer(prize);
        
        emit RoundCompleted(round.roundId, winner, round.totalPot, prize, publisherCommission, sparsityCommission, randomSeed);
    }
    
    /**
     * @dev Cancel an active round (emergency function)
     * @param roundId The ID of the round to cancel
     * @param reason Reason for cancellation
     */
    function cancelRound(uint256 roundId, string calldata reason) external onlyOperator validRound(roundId) roundExists(roundId) {
        LotteryRound storage round = rounds[roundId];
        
        require(!round.completed, "Cannot cancel completed round");
        require(!round.cancelled, "Round already cancelled");
        
        round.cancelled = true;
        hasActiveRound = false;
        
        // Refund all participants
        uint256 totalRefunded = _refundParticipants(roundId);
        
        emit RoundCancelled(roundId, reason, totalRefunded);
    }
    
    // =============== PLAYER FUNCTIONS ===============
    
    /**
     * @dev Place a bet in the current active round
     * @notice Players can place multiple bets, minimum bet amount required
     */
    function placeBet() external payable {
        require(hasActiveRound, "No active round");
        require(msg.value >= minBetAmount, "Bet amount too low");
        
        LotteryRound storage round = rounds[currentRoundId];
        require(block.timestamp >= round.startTime, "Betting not started");
        require(block.timestamp <= round.endTime, "Betting period ended");
        require(!round.completed && !round.cancelled, "Round not active");
        
        // Add to participant list if first bet
        if (!hasParticipated[currentRoundId][msg.sender]) {
            roundParticipants[currentRoundId].push(msg.sender);
            hasParticipated[currentRoundId][msg.sender] = true;
            round.participantCount++;
        }
        
        // Update bet amount and total pot
        roundBets[currentRoundId][msg.sender] += msg.value;
        round.totalPot += msg.value;
        
        emit BetPlaced(currentRoundId, msg.sender, msg.value, round.totalPot, block.timestamp);
    }
    
    // =============== PUBLIC FUNCTIONS ===============
    
    /**
     * @dev Refund participants of an expired round
     * @param roundId The ID of the round to refund
     * @notice Anyone can call this if draw time has passed without completion
     */
    function refundExpiredRound(uint256 roundId) external validRound(roundId) roundExists(roundId) {
        LotteryRound storage round = rounds[roundId];
        
        require(!round.completed, "Round already completed");
        require(!round.cancelled, "Round already cancelled");
        require(!round.refunded, "Round already refunded");
        require(block.timestamp > round.drawTime + 3600, "Grace period not expired"); // 1 hour grace
        
        round.refunded = true;
        if (roundId == currentRoundId) {
            hasActiveRound = false;
        }
        
        uint256 totalRefunded = _refundParticipants(roundId);
        
        emit RoundRefunded(roundId, totalRefunded, round.participantCount);
    }
    
    // =============== INTERNAL FUNCTIONS ===============
    
    /**
     * @dev Internal function to refund all participants of a round
     * @param roundId The ID of the round to refund
     * @return totalRefunded Total amount refunded
     */
    function _refundParticipants(uint256 roundId) internal returns (uint256 totalRefunded) {
        address[] memory participants = roundParticipants[roundId];
        
        for (uint256 i = 0; i < participants.length; i++) {
            address participant = participants[i];
            uint256 betAmount = roundBets[roundId][participant];
            
            if (betAmount > 0) {
                roundBets[roundId][participant] = 0; // Prevent re-entrancy
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
    function getCurrentRound() external view returns (LotteryRound memory) {
        if (hasActiveRound && currentRoundId > 0) {
            return rounds[currentRoundId];
        }
        // Return empty round if no active round
        return LotteryRound(0, 0, 0, 0, 0, 0, address(0), 0, 0, 0, false, false, false);
    }
    
    /**
     * @dev Get round participants
     * @param roundId The ID of the round
     */
    function getRoundParticipants(uint256 roundId) external view validRound(roundId) returns (address[] memory) {
        return roundParticipants[roundId];
    }
    
    /**
     * @dev Get player's bet amount for a specific round
     * @param roundId The ID of the round
     * @param player The player's address
     */
    function getPlayerBet(uint256 roundId, address player) external view validRound(roundId) returns (uint256) {
        return roundBets[roundId][player];
    }
    
    /**
     * @dev Check if current round can be drawn
     */
    function canDrawCurrentRound() external view returns (bool) {
        if (!hasActiveRound || currentRoundId == 0) return false;
        
        LotteryRound memory round = rounds[currentRoundId];
        return (
            !round.completed &&
            !round.cancelled &&
            block.timestamp >= round.drawTime &&
            round.participantCount >= minParticipants &&
            round.totalPot > 0
        );
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
        uint256 drawDelay,
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
            drawDelayAfterEnd,
            minParticipants,
            sparsitySet
        );
    }
}
