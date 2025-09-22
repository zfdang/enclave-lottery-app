// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title Lottery Contract
 * @dev Smart contract for managing lottery draws and user bets
 */
contract Lottery {
    struct Bet {
        address user;
        uint256 amount;
        uint256 timestamp;
        uint256 blockNumber;
    }
    
    struct Draw {
        string drawId;
        uint256 startTime;
        uint256 endTime;
        uint256 drawTime;
        uint256 totalPot;
        bool isActive;
        bool isCompleted;
        address winner;
        uint256 winningNumber;
        uint256 completedTimestamp;
        bool exists;
    }
    
    // Mappings
    mapping(string => Draw) public draws;
    mapping(string => Bet[]) public drawBets;
    mapping(string => mapping(address => uint256)) public userBetCount;
    mapping(address => uint256) public userTotalBets;
    
    // Arrays for enumeration
    string[] public drawIds;
    string[] public activeDrawIds;
    
    // Contract settings
    address public owner;
    address public enclaveAddress;
    uint256 public minimumBet = 0.001 ether;
    uint256 public maximumBet = 10 ether;
    uint256 public maxBetsPerUser = 10;
    
    // Events
    event DrawCreated(
        string indexed drawId,
        uint256 startTime,
        uint256 endTime,
        uint256 drawTime
    );
    
    event BetPlaced(
        string indexed drawId,
        address indexed user,
        uint256 amount,
        uint256 timestamp,
        uint256 betIndex
    );
    
    event DrawCompleted(
        string indexed drawId,
        address indexed winner,
        uint256 winningNumber,
        uint256 totalPot,
        uint256 timestamp
    );
    
    event EnclaveAddressUpdated(address indexed oldAddress, address indexed newAddress);
    event SettingsUpdated(uint256 minimumBet, uint256 maximumBet, uint256 maxBetsPerUser);
    
    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner can call this function");
        _;
    }
    
    modifier onlyEnclave() {
        require(msg.sender == enclaveAddress, "Only enclave can call this function");
        _;
    }
    
    constructor() {
        owner = msg.sender;
        enclaveAddress = msg.sender; // Initially set to deployer
    }
    
    /**
     * @dev Set the enclave address that can manage draws
     * @param _enclaveAddress The address of the enclave
     */
    function setEnclaveAddress(address _enclaveAddress) external onlyOwner {
        address oldAddress = enclaveAddress;
        enclaveAddress = _enclaveAddress;
        emit EnclaveAddressUpdated(oldAddress, _enclaveAddress);
    }
    
    /**
     * @dev Update contract settings
     */
    function updateSettings(
        uint256 _minimumBet,
        uint256 _maximumBet,
        uint256 _maxBetsPerUser
    ) external onlyOwner {
        require(_minimumBet > 0, "Minimum bet must be positive");
        require(_maximumBet >= _minimumBet, "Maximum bet must be >= minimum bet");
        require(_maxBetsPerUser > 0, "Max bets per user must be positive");
        
        minimumBet = _minimumBet;
        maximumBet = _maximumBet;
        maxBetsPerUser = _maxBetsPerUser;
        
        emit SettingsUpdated(_minimumBet, _maximumBet, _maxBetsPerUser);
    }
    
    /**
     * @dev Create a new lottery draw
     */
    function createDraw(
        string memory drawId,
        uint256 startTime,
        uint256 endTime,
        uint256 drawTime
    ) external onlyEnclave {
        require(!draws[drawId].exists, "Draw already exists");
        require(startTime < endTime, "Start time must be before end time");
        require(endTime < drawTime, "End time must be before draw time");
        require(startTime >= block.timestamp, "Start time must be in the future");
        
        draws[drawId] = Draw({
            drawId: drawId,
            startTime: startTime,
            endTime: endTime,
            drawTime: drawTime,
            totalPot: 0,
            isActive: true,
            isCompleted: false,
            winner: address(0),
            winningNumber: 0,
            completedTimestamp: 0,
            exists: true
        });
        
        drawIds.push(drawId);
        activeDrawIds.push(drawId);
        
        emit DrawCreated(drawId, startTime, endTime, drawTime);
    }
    /**
     * @dev Place a bet in the current active draw
     * @param drawId The ID of the draw to bet on
     */
    function placeBet(string memory drawId) external payable {
        require(draws[drawId].exists, "Draw does not exist");
        require(draws[drawId].isActive, "Draw is not active");
        require(!draws[drawId].isCompleted, "Draw is already completed");
        require(block.timestamp >= draws[drawId].startTime, "Draw has not started yet");
        require(block.timestamp <= draws[drawId].endTime, "Betting period has ended");
        require(msg.value >= minimumBet, "Bet amount too low");
        require(msg.value <= maximumBet, "Bet amount too high");
        require(userBetCount[drawId][msg.sender] < maxBetsPerUser, "Maximum bets per user exceeded");
        
        // Create the bet
        Bet memory newBet = Bet({
            user: msg.sender,
            amount: msg.value,
            timestamp: block.timestamp,
            blockNumber: block.number
        });
        
        drawBets[drawId].push(newBet);
        userBetCount[drawId][msg.sender]++;
        userTotalBets[msg.sender]++;
        draws[drawId].totalPot += msg.value;
        
        emit BetPlaced(drawId, msg.sender, msg.value, block.timestamp, drawBets[drawId].length - 1);
    }
    
    /**
     * @dev Complete a draw with results (only enclave can call)
     */
    function completeDraw(
        string memory drawId,
        address winner,
        uint256 winningNumber
    ) external onlyEnclave {
        require(draws[drawId].exists, "Draw does not exist");
        require(draws[drawId].isActive, "Draw is not active");
        require(!draws[drawId].isCompleted, "Draw is already completed");
        require(block.timestamp >= draws[drawId].drawTime, "Draw time has not been reached");
        
        draws[drawId].isActive = false;
        draws[drawId].isCompleted = true;
        draws[drawId].winner = winner;
        draws[drawId].winningNumber = winningNumber;
        draws[drawId].completedTimestamp = block.timestamp;
        
        // Remove from active draws
        _removeFromActiveDraws(drawId);
        
        // Transfer prize to winner if there is one
        if (winner != address(0) && draws[drawId].totalPot > 0) {
            payable(winner).transfer(draws[drawId].totalPot);
        }
        
        emit DrawCompleted(drawId, winner, winningNumber, draws[drawId].totalPot, block.timestamp);
    }
    
    /**
     * @dev Get draw information
     */
    function getDraw(string memory drawId) external view returns (
        string memory,
        uint256,
        uint256,
        uint256,
        uint256,
        bool,
        bool,
        address,
        uint256
    ) {
        require(draws[drawId].exists, "Draw does not exist");
        Draw memory draw = draws[drawId];
        return (
            draw.drawId,
            draw.startTime,
            draw.endTime,
            draw.drawTime,
            draw.totalPot,
            draw.isActive,
            draw.isCompleted,
            draw.winner,
            draw.winningNumber
        );
    }
    
    /**
     * @dev Get bets for a specific draw
     */
    function getDrawBets(string memory drawId) external view returns (
        address[] memory users,
        uint256[] memory amounts,
        uint256[] memory timestamps
    ) {
        require(draws[drawId].exists, "Draw does not exist");
        
        Bet[] memory bets = drawBets[drawId];
        uint256 betCount = bets.length;
        
        users = new address[](betCount);
        amounts = new uint256[](betCount);
        timestamps = new uint256[](betCount);
        
        for (uint256 i = 0; i < betCount; i++) {
            users[i] = bets[i].user;
            amounts[i] = bets[i].amount;
            timestamps[i] = bets[i].timestamp;
        }
    }
    
    /**
     * @dev Get user's bets for a specific draw
     */
    function getUserBets(string memory drawId, address user) external view returns (
        uint256[] memory amounts,
        uint256[] memory timestamps,
        uint256[] memory indices
    ) {
        require(draws[drawId].exists, "Draw does not exist");
        
        Bet[] memory bets = drawBets[drawId];
        uint256 userBetCountForDraw = userBetCount[drawId][user];
        
        amounts = new uint256[](userBetCountForDraw);
        timestamps = new uint256[](userBetCountForDraw);
        indices = new uint256[](userBetCountForDraw);
        
        uint256 userBetIndex = 0;
        for (uint256 i = 0; i < bets.length; i++) {
            if (bets[i].user == user) {
                amounts[userBetIndex] = bets[i].amount;
                timestamps[userBetIndex] = bets[i].timestamp;
                indices[userBetIndex] = i;
                userBetIndex++;
            }
        }
    }
    
    /**
     * @dev Get active draws
     */
    function getActiveDraws() external view returns (string[] memory) {
        return activeDrawIds;
    }
    
    /**
     * @dev Get total number of draws
     */
    function getDrawCount() external view returns (uint256) {
        return drawIds.length;
    }
    
    /**
     * @dev Get total number of bets for a draw
     */
    function getDrawBetCount(string memory drawId) external view returns (uint256) {
        require(draws[drawId].exists, "Draw does not exist");
        return drawBets[drawId].length;
    }
    
    /**
     * @dev Emergency function to withdraw funds (only owner)
     */
    function emergencyWithdraw() external onlyOwner {
        payable(owner).transfer(address(this).balance);
    }
    
    /**
     * @dev Internal function to remove draw from active draws array
     */
    function _removeFromActiveDraws(string memory drawId) internal {
        for (uint256 i = 0; i < activeDrawIds.length; i++) {
            if (keccak256(bytes(activeDrawIds[i])) == keccak256(bytes(drawId))) {
                activeDrawIds[i] = activeDrawIds[activeDrawIds.length - 1];
                activeDrawIds.pop();
                break;
            }
        }
    }
    
    /**
     * @dev Get contract balance
     */
    function getContractBalance() external view returns (uint256) {
        return address(this).balance;
    }
}