import { ethers } from 'ethers'
import { useWalletStore } from './wallet'

// Lottery contract ABI (minimal interface for betting)
const LOTTERY_ABI = [
  // Events
  'event DrawCreated(string indexed drawId, uint256 startTime, uint256 endTime, uint256 drawTime)',
  'event BetPlaced(string indexed drawId, address indexed user, uint256 amount, uint256 timestamp, uint256 betIndex)',
  'event DrawCompleted(string indexed drawId, address indexed winner, uint256 winningNumber, uint256 totalPot, uint256 timestamp)',
  
  // Functions
  'function placeBet(string memory drawId) external payable',
  'function getDraw(string memory drawId) external view returns (string memory, uint256, uint256, uint256, uint256, bool, bool, address, uint256)',
  'function getDrawBets(string memory drawId) external view returns (address[] memory, uint256[] memory, uint256[] memory)',
  'function getUserBets(string memory drawId, address user) external view returns (uint256[] memory, uint256[] memory, uint256[] memory)',
  'function getActiveDraws() external view returns (string[] memory)',
  'function getDrawCount() external view returns (uint256)',
  'function getDrawBetCount(string memory drawId) external view returns (uint256)',
  'function getContractBalance() external view returns (uint256)',
  'function minimumBet() external view returns (uint256)',
  'function maximumBet() external view returns (uint256)',
  'function maxBetsPerUser() external view returns (uint256)',
  'function userBetCount(string memory drawId, address user) external view returns (uint256)'
]

interface Draw {
  drawId: string
  startTime: number
  endTime: number
  drawTime: number
  totalPot: string
  isActive: boolean
  isCompleted: boolean
  winner: string
  winningNumber: number
}

interface Bet {
  user: string
  amount: string
  timestamp: number
  index: number
}

class ContractService {
  private contract: ethers.Contract | null = null
  private contractAddress: string = ''

  constructor() {
    // Get contract address from environment or config
    this.contractAddress = process.env.REACT_APP_LOTTERY_CONTRACT_ADDRESS || ''
  }

  private getContract(): ethers.Contract {
    const { provider, signer } = useWalletStore.getState()
    
    if (!provider) {
      throw new Error('Wallet not connected')
    }

    if (!this.contractAddress) {
      throw new Error('Contract address not configured')
    }

    // Use signer for write operations, provider for read operations
    const signerOrProvider = signer || provider
    
    if (!this.contract) {
      this.contract = new ethers.Contract(this.contractAddress, LOTTERY_ABI, signerOrProvider)
    }

    return this.contract
  }

  /**
   * Place a bet on a specific draw
   */
  async placeBet(drawId: string, betAmount: string): Promise<string> {
    const contract = this.getContract()
    const { signer } = useWalletStore.getState()

    if (!signer) {
      throw new Error('Wallet not connected')
    }

    try {
      // Validate bet amount against contract limits
      const minBet = await contract.minimumBet()
      const maxBet = await contract.maximumBet()
      const betAmountWei = ethers.parseEther(betAmount)

      if (betAmountWei < minBet) {
        throw new Error(`Bet amount must be at least ${ethers.formatEther(minBet)} ETH`)
      }

      if (betAmountWei > maxBet) {
        throw new Error(`Bet amount cannot exceed ${ethers.formatEther(maxBet)} ETH`)
      }

      // Check user's bet count for this draw
      const { address } = useWalletStore.getState()
      if (address) {
        const userBets = await contract.userBetCount(drawId, address)
        const maxBets = await contract.maxBetsPerUser()
        
        if (userBets >= maxBets) {
          throw new Error(`You can only place up to ${maxBets} bets per draw`)
        }
      }

      // Place the bet
      const tx = await contract.placeBet(drawId, { value: betAmountWei })
      const receipt = await tx.wait()

      // Update wallet balance
      useWalletStore.getState().updateBalance()

      return receipt.hash
    } catch (error: any) {
      if (error.code === 4001) {
        throw new Error('Transaction was rejected by user')
      } else if (error.message.includes('revert')) {
        // Extract revert reason
        const reason = error.message.match(/revert (.+)/)?.[1] || 'Transaction failed'
        throw new Error(reason)
      } else {
        throw new Error('Transaction failed: ' + (error.message || 'Unknown error'))
      }
    }
  }

  /**
   * Get draw information
   */
  async getDraw(drawId: string): Promise<Draw> {
    const contract = this.getContract()

    try {
      const result = await contract.getDraw(drawId)
      
      return {
        drawId: result[0],
        startTime: Number(result[1]),
        endTime: Number(result[2]),
        drawTime: Number(result[3]),
        totalPot: ethers.formatEther(result[4]),
        isActive: result[5],
        isCompleted: result[6],
        winner: result[7],
        winningNumber: Number(result[8])
      }
    } catch (error: any) {
      throw new Error('Failed to get draw information: ' + (error.message || 'Unknown error'))
    }
  }

  /**
   * Get all bets for a draw
   */
  async getDrawBets(drawId: string): Promise<Bet[]> {
    const contract = this.getContract()

    try {
      const result = await contract.getDrawBets(drawId)
      const [users, amounts, timestamps] = result

      return users.map((user: string, index: number) => ({
        user,
        amount: ethers.formatEther(amounts[index]),
        timestamp: Number(timestamps[index]),
        index
      }))
    } catch (error: any) {
      throw new Error('Failed to get draw bets: ' + (error.message || 'Unknown error'))
    }
  }

  /**
   * Get user's bets for a specific draw
   */
  async getUserBets(drawId: string, userAddress?: string): Promise<Bet[]> {
    const contract = this.getContract()
    const address = userAddress || useWalletStore.getState().address

    if (!address) {
      throw new Error('No user address provided')
    }

    try {
      const result = await contract.getUserBets(drawId, address)
      const [amounts, timestamps, indices] = result

      return amounts.map((amount: bigint, index: number) => ({
        user: address,
        amount: ethers.formatEther(amount),
        timestamp: Number(timestamps[index]),
        index: Number(indices[index])
      }))
    } catch (error: any) {
      throw new Error('Failed to get user bets: ' + (error.message || 'Unknown error'))
    }
  }

  /**
   * Get active draws
   */
  async getActiveDraws(): Promise<string[]> {
    const contract = this.getContract()

    try {
      return await contract.getActiveDraws()
    } catch (error: any) {
      throw new Error('Failed to get active draws: ' + (error.message || 'Unknown error'))
    }
  }

  /**
   * Get total draw count
   */
  async getDrawCount(): Promise<number> {
    const contract = this.getContract()

    try {
      const count = await contract.getDrawCount()
      return Number(count)
    } catch (error: any) {
      throw new Error('Failed to get draw count: ' + (error.message || 'Unknown error'))
    }
  }

  /**
   * Get bet count for a specific draw
   */
  async getDrawBetCount(drawId: string): Promise<number> {
    const contract = this.getContract()

    try {
      const count = await contract.getDrawBetCount(drawId)
      return Number(count)
    } catch (error: any) {
      throw new Error('Failed to get draw bet count: ' + (error.message || 'Unknown error'))
    }
  }

  /**
   * Get contract balance
   */
  async getContractBalance(): Promise<string> {
    const contract = this.getContract()

    try {
      const balance = await contract.getContractBalance()
      return ethers.formatEther(balance)
    } catch (error: any) {
      throw new Error('Failed to get contract balance: ' + (error.message || 'Unknown error'))
    }
  }

  /**
   * Get contract betting limits
   */
  async getBettingLimits(): Promise<{ min: string; max: string; maxBetsPerUser: number }> {
    const contract = this.getContract()

    try {
      const [minBet, maxBet, maxBetsPerUser] = await Promise.all([
        contract.minimumBet(),
        contract.maximumBet(),
        contract.maxBetsPerUser()
      ])

      return {
        min: ethers.formatEther(minBet),
        max: ethers.formatEther(maxBet),
        maxBetsPerUser: Number(maxBetsPerUser)
      }
    } catch (error: any) {
      throw new Error('Failed to get betting limits: ' + (error.message || 'Unknown error'))
    }
  }

  /**
   * Subscribe to contract events
   */
  subscribeToEvents(callbacks: {
    onDrawCreated?: (drawId: string, startTime: number, endTime: number, drawTime: number) => void
    onBetPlaced?: (drawId: string, user: string, amount: string, timestamp: number, betIndex: number) => void
    onDrawCompleted?: (drawId: string, winner: string, winningNumber: number, totalPot: string, timestamp: number) => void
  }) {
    const contract = this.getContract()

    if (callbacks.onDrawCreated) {
      contract.on('DrawCreated', (drawId, startTime, endTime, drawTime) => {
        callbacks.onDrawCreated!(drawId, Number(startTime), Number(endTime), Number(drawTime))
      })
    }

    if (callbacks.onBetPlaced) {
      contract.on('BetPlaced', (drawId, user, amount, timestamp, betIndex) => {
        callbacks.onBetPlaced!(drawId, user, ethers.formatEther(amount), Number(timestamp), Number(betIndex))
      })
    }

    if (callbacks.onDrawCompleted) {
      contract.on('DrawCompleted', (drawId, winner, winningNumber, totalPot, timestamp) => {
        callbacks.onDrawCompleted!(drawId, winner, Number(winningNumber), ethers.formatEther(totalPot), Number(timestamp))
      })
    }

    // Return cleanup function
    return () => {
      contract.removeAllListeners()
    }
  }
}

export const contractService = new ContractService()
export type { Draw, Bet }