// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title Lottery Contract
 * @dev Smart contract for recording lottery draws and results
 */
contract Lottery {
    struct Draw {
        string drawId;
        address winner;
        uint256 winningNumber;
        uint256 totalPot;
        uint256 timestamp;
        bool exists;
    }
    
    mapping(string => Draw) public draws;
    string[] public drawIds;
    
    address public owner;
    address public enclaveAddress;
    
    event DrawRecorded(
        string indexed drawId,
        address indexed winner,
        uint256 winningNumber,
        uint256 totalPot,
        uint256 timestamp
    );
    
    event EnclaveAddressUpdated(address indexed oldAddress, address indexed newAddress);
    
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
     * @dev Set the enclave address that can record draws
     * @param _enclaveAddress The address of the enclave
     */
    function setEnclaveAddress(address _enclaveAddress) external onlyOwner {
        address oldAddress = enclaveAddress;
        enclaveAddress = _enclaveAddress;
        emit EnclaveAddressUpdated(oldAddress, _enclaveAddress);
    }
    
    /**
     * @dev Record a lottery draw result
     * @param drawId Unique identifier for the draw
     * @param winner Address of the winner (can be zero address if no winner)
     * @param winningNumber The winning number
     * @param totalPot Total pot amount in wei
     */
    function recordDraw(
        string memory drawId,
        address winner,
        uint256 winningNumber,
        uint256 totalPot
    ) external onlyEnclave {
        require(!draws[drawId].exists, "Draw already recorded");
        
        draws[drawId] = Draw({
            drawId: drawId,
            winner: winner,
            winningNumber: winningNumber,
            totalPot: totalPot,
            timestamp: block.timestamp,
            exists: true
        });
        
        drawIds.push(drawId);
        
        emit DrawRecorded(drawId, winner, winningNumber, totalPot, block.timestamp);
    }
    
    /**
     * @dev Get draw information by ID
     * @param drawId The draw ID to query
     */
    function getDraw(string memory drawId) external view returns (
        string memory,
        address,
        uint256,
        uint256,
        uint256
    ) {
        require(draws[drawId].exists, "Draw does not exist");
        Draw memory draw = draws[drawId];
        return (draw.drawId, draw.winner, draw.winningNumber, draw.totalPot, draw.timestamp);
    }
    
    /**
     * @dev Get the total number of recorded draws
     */
    function getDrawCount() external view returns (uint256) {
        return drawIds.length;
    }
    
    /**
     * @dev Get draw ID by index
     * @param index The index to query
     */
    function getDrawIdByIndex(uint256 index) external view returns (string memory) {
        require(index < drawIds.length, "Index out of bounds");
        return drawIds[index];
    }
    
    /**
     * @dev Get recent draws (up to last 10)
     */
    function getRecentDraws() external view returns (
        string[] memory ids,
        address[] memory winners,
        uint256[] memory winningNumbers,
        uint256[] memory totalPots,
        uint256[] memory timestamps
    ) {
        uint256 count = drawIds.length;
        uint256 limit = count > 10 ? 10 : count;
        
        ids = new string[](limit);
        winners = new address[](limit);
        winningNumbers = new uint256[](limit);
        totalPots = new uint256[](limit);
        timestamps = new uint256[](limit);
        
        for (uint256 i = 0; i < limit; i++) {
            string memory drawId = drawIds[count - 1 - i];
            Draw memory draw = draws[drawId];
            
            ids[i] = draw.drawId;
            winners[i] = draw.winner;
            winningNumbers[i] = draw.winningNumber;
            totalPots[i] = draw.totalPot;
            timestamps[i] = draw.timestamp;
        }
    }
    
    /**
     * @dev Check if a draw exists
     * @param drawId The draw ID to check
     */
    function drawExists(string memory drawId) external view returns (bool) {
        return draws[drawId].exists;
    }
}