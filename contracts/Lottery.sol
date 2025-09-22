// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title Lottery Contract - Role-based Architecture
 * @dev Smart contract for managing lottery rounds with admin/operator/player roles
 * @notice Admin deploys and configures, Operator manages rounds, Players place bets
 */
contract Lottery {
    // =============== ROLES ===============
    address public immutable admin;
    address public operator;
    
    // =============== IMMUTABLE CONFIGURATION ===============
    uint256 public immutable adminCommissionRate; // Basis points (500 = 5%)
    uint256 public immutable minBetAmount; // Minimum bet in wei
    uint256 public immutable bettingDuration; // Betting period in seconds
    uint256 public immutable drawDelayAfterEnd; // Grace period before draw in seconds
    uint256 public immutable minParticipants; // Minimum players required (2)
    
    // =============== STRUCTS ===============
    struct LotteryRound {
        uint256 roundId;
        uint256 startTime;
        uint256 endTime;
        uint256 drawTime;
        uint256 totalPot;
        uint256 participantCount;
        address winner;
        uint256 adminCommission;
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
        uint256 adminCommission,
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
    
    // =============== MODIFIERS ===============
    modifier onlyAdmin() {
        require(msg.sender == admin, "Only admin can call this function");
        _;
    }
    
    modifier onlyOperator() {
        require(operator != address(0), "Operator not set");
        require(msg.sender == operator, "Only operator can call this function");
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
        uint256 _adminCommissionRate,
        uint256 _minBetAmount,
        uint256 _bettingDuration,
        uint256 _drawDelayAfterEnd
    ) {
        require(_adminCommissionRate <= 1000, "Commission rate too high (max 10%)");
        require(_minBetAmount > 0, "Minimum bet must be positive");
        require(_bettingDuration >= 300, "Betting duration too short (min 5 minutes)");
        require(_drawDelayAfterEnd >= 60, "Draw delay too short (min 1 minute)");
        
        admin = msg.sender;
        operator = address(0); // Operator will be set later by admin
        adminCommissionRate = _adminCommissionRate;
        minBetAmount = _minBetAmount;
        bettingDuration = _bettingDuration;
        drawDelayAfterEnd = _drawDelayAfterEnd;
        minParticipants = 2;
        
        currentRoundId = 0;
        totalRounds = 0;
        hasActiveRound = false;
    }
    
    // =============== ADMIN FUNCTIONS ===============
    
    /**
     * @dev Set the operator address
     * @param _operator The address of the operator
     * @notice Can only be called by admin, and only when no operator is set or no active round exists
     */
    function setOperator(address _operator) external onlyAdmin {
        require(_operator != address(0), "Invalid operator address");
        require(!hasActiveRound, "Cannot change operator during active round");
        
        operator = _operator;
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
            adminCommission: 0,
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
            block.difficulty,
            block.number,
            roundId,
            round.totalPot
        )));
        
        uint256 winnerIndex = randomSeed % round.participantCount;
        address winner = roundParticipants[roundId][winnerIndex];
        
        // Calculate payouts
        uint256 commission = (round.totalPot * adminCommissionRate) / 10000;
        uint256 prize = round.totalPot - commission;
        
        // Update round state
        round.winner = winner;
        round.adminCommission = commission;
        round.winnerPrize = prize;
        round.completed = true;
        hasActiveRound = false;
        
        // Transfer funds
        if (commission > 0) {
            payable(admin).transfer(commission);
        }
        payable(winner).transfer(prize);
        
        emit RoundCompleted(roundId, winner, round.totalPot, prize, commission, randomSeed);
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
        return LotteryRound(0, 0, 0, 0, 0, 0, address(0), 0, 0, false, false, false);
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
        address adminAddr,
        address operatorAddr,
        uint256 commissionRate,
        uint256 minBet,
        uint256 bettingDur,
        uint256 drawDelay,
        uint256 minPart
    ) {
        return (
            admin,
            operator,
            adminCommissionRate,
            minBetAmount,
            bettingDuration,
            drawDelayAfterEnd,
            minParticipants
        );
    }
}
