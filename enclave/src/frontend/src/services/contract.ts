import { ethers, isAddress } from 'ethers'
import { useWalletStore } from './wallet'

// Lottery contract ABI based on the current Lottery.sol
const LOTTERY_ABI = [
  // Events
  'event RoundCreated(uint256 indexed roundId, uint256 startTime, uint256 endTime, uint256 minDrawTime, uint256 maxDrawTime)',
  'event BetPlaced(uint256 indexed roundId, address indexed player, uint256 amount, uint256 newTotal, uint256 timestamp)',
  'event EndTimeExtended(uint256 indexed roundId, uint256 oldEndTime, uint256 newEndTime)',
  'event RoundStateChanged(uint256 indexed roundId, uint8 oldState, uint8 newState)',
  'event RoundCompleted(uint256 indexed roundId, address indexed winner, uint256 totalPot, uint256 winnerPrize, uint256 publisherCommission, uint256 sparsityCommission, uint256 randomSeed)',
  'event RoundRefunded(uint256 indexed roundId, uint256 totalRefunded, uint256 participantCount, string reason)',
  'event MinBetAmountUpdated(uint256 oldAmount, uint256 newAmount)',
  'event SparsitySet(address indexed sparsity)',
  'event OperatorUpdated(address indexed oldOperator, address indexed newOperator)',

  // Public state variables
  'function publisher() view returns (address)',
  'function sparsity() view returns (address)',
  'function operator() view returns (address)',
  'function publisherCommissionRate() view returns (uint256)',
  'function sparsityCommissionRate() view returns (uint256)',
  'function minBetAmount() view returns (uint256)',
  'function bettingDuration() view returns (uint256)',
  'function minDrawDelayAfterEnd() view returns (uint256)',
  'function maxDrawDelayAfterEnd() view returns (uint256)',
  'function minEndTimeExtension() view returns (uint256)',
  'function minParticipants() view returns (uint256)',

  // Round and helpers
  'function round() view returns (tuple(uint256 roundId, uint256 startTime, uint256 endTime, uint256 minDrawTime, uint256 maxDrawTime, uint256 totalPot, uint256 participantCount, address winner, uint256 publisherCommission, uint256 sparsityCommission, uint256 winnerPrize, uint8 state))',
  'function getRound() view returns (tuple(uint256 roundId, uint256 startTime, uint256 endTime, uint256 minDrawTime, uint256 maxDrawTime, uint256 totalPot, uint256 participantCount, address winner, uint256 publisherCommission, uint256 sparsityCommission, uint256 winnerPrize, uint8 state))',

  // Participants and bets
  'function getParticipants() view returns (address[])',
  'function getBetAmount(address player) view returns (uint256)',
  'function bets(address) view returns (uint256)',
  'function participants(uint256) view returns (address)',

  // Player functions
  'function placeBet() payable',

  // Publisher/Sparsity/Operator functions
  'function setSparsity(address)',
  'function updateOperator(address)',
  'function updateMinBetAmount(uint256)',
  'function startNewRound()',
  'function extendBettingTime(uint256)',
  'function refundRound()',
  'function drawWinner()',

  // Public functions
  'function refundExpiredRound()'
]

// RoundState enum mapping (uppercase to match contract)
export enum RoundState {
  WAITING = 0,
  BETTING = 1,
  DRAWING = 2,
  COMPLETED = 3,
  REFUNDED = 4
}

export interface LotteryRound {
  roundId: number
  startTime: number
  endTime: number
  minDrawTime: number
  maxDrawTime: number
  totalPot: string
  participantCount: number
  winner: string
  publisherCommission: string
  sparsityCommission: string
  winnerPrize: string
  state: RoundState
}

export interface ContractConfig {
  publisherAddr: string
  sparsityAddr: string
  operatorAddr: string
  publisherCommission: string
  sparsityCommission: string
  minBet: string
  bettingDur: string
  minDrawDelay: string
  maxDrawDelay: string
  minEndTimeExt: string
  minParticipants: string
}

export interface RoundTiming {
  startTime: number
  endTime: number
  minDrawTime: number
  maxDrawTime: number
  currentTime: number
}

class ContractService {
  private contract: ethers.Contract | null = null
  private contractAddress: string = ''
  private cachedAbi: any | null = null
  rpcUrl: string
  chainId: number | undefined

  constructor() {
    // Get contract address from environment or config (Vite uses import.meta.env)
    this.contractAddress = import.meta.env.VITE_LOTTERY_CONTRACT_ADDRESS || ''
    this.rpcUrl = import.meta.env.VITE_RPC_URL || ''
    this.chainId = import.meta.env.VITE_CHAIN_ID ? Number(import.meta.env.VITE_CHAIN_ID) : undefined
    console.log('ContractService initialized with address:', this.contractAddress + ', rpcUrl:', this.rpcUrl + ', chainId:', this.chainId)
  }

  /**
   * Set or update the configured contract address used by this service.
   * Passing a falsy value (null or empty string) will clear the configured address.
   */
  setContractAddress(address: string | null) {
    if (!address) {
      this.contractAddress = ''
      this.contract = null
      return
    }

    if (!isAddress(address)) {
      throw new Error('Invalid Ethereum address')
    }

    this.contractAddress = address
    // Clear cached contract so it will be recreated with the new address
    this.contract = null
  }

  /**
   * Return true if a configured contract address looks valid (non-empty and a valid ETH address).
   */
  hasValidContractAddress(): boolean {
    return !!this.contractAddress && isAddress(this.contractAddress)
  }

  /**
   * Load the contract ABI from the public location and cache it.
   */
  private async loadAbi(): Promise<any> {
    if (this.cachedAbi) return this.cachedAbi

    const abiRes = await fetch('/contracts/abi/Lottery.abi')
    if (!abiRes.ok) throw new Error('Failed to fetch ABI')
    const abiText = await abiRes.text()
    this.cachedAbi = JSON.parse(abiText)
    return this.cachedAbi
  }


  private getContract(contractAddress?: string): ethers.Contract {
    const { provider, signer } = useWalletStore.getState()
    
    if (!provider) {
      throw new Error('Wallet not connected')
    }

    const address = contractAddress || this.contractAddress
    if (!address) {
      throw new Error('Contract address not configured')
    }

    // Use signer for write operations, provider for read operations
    const signerOrProvider = signer || provider
    
    return new ethers.Contract(address, LOTTERY_ABI, signerOrProvider)
  }


  /**
   * Place a bet on the current lottery round
   */
  async placeBet(betAmount: string): Promise<string> {
    const contract = this.getContract()
    const { signer } = useWalletStore.getState()

    if (!signer) {
      throw new Error('Wallet not connected')
    }

    try {
      // Validate bet amount against contract minimum
      const minBet = await contract.minBetAmount()
      const betAmountWei = ethers.parseEther(betAmount)

      if (betAmountWei < minBet) {
        throw new Error(`Bet amount must be at least ${ethers.formatEther(minBet)} ETH`)
      }

      // Place the bet
      const tx = await contract.placeBet({ value: betAmountWei })
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
   * Get current lottery state
   */
  async getState(): Promise<RoundState> {
    const contract = this.getContract()

    try {
      const r = await contract.getRound()
      return Number(r.state) as RoundState
    } catch (error: any) {
      throw new Error('Failed to get lottery state: ' + (error.message || 'Unknown error'))
    }
  }

  /**
   * Get current round participants
   */
  async getParticipants(): Promise<string[]> {
    const contract = this.getContract()

    try {
      return await contract.getParticipants()
    } catch (error: any) {
      throw new Error('Failed to get participants: ' + (error.message || 'Unknown error'))
    }
  }

  /**
   * Get player's bet amount for current round
   */
  async getPlayerBet(playerAddress?: string): Promise<string> {
    const contract = this.getContract()
    const address = playerAddress || useWalletStore.getState().address

    if (!address) {
      throw new Error('No player address provided')
    }

    try {
      // Lottery.sol exposes getBetAmount(address) for player bets
      const betAmount = await contract.getBetAmount(address)
      return ethers.formatEther(betAmount)
    } catch (error: any) {
      throw new Error('Failed to get player bet: ' + (error.message || 'Unknown error'))
    }
  }

  /**
   * Get player's bet amount for current round using mapping
   */
  async getBets(playerAddress?: string): Promise<string> {
    const contract = this.getContract()
    const address = playerAddress || useWalletStore.getState().address

    if (!address) {
      throw new Error('No player address provided')
    }

    try {
      const betAmount = await contract.bets(address)
      return ethers.formatEther(betAmount)
    } catch (error: any) {
      throw new Error('Failed to get player bets: ' + (error.message || 'Unknown error'))
    }
  }

  /**
   * Check if current round can be drawn
   */
  async canDraw(): Promise<boolean> {
    // Determine draw eligibility from on-chain round state and timing
    const contract = this.getContract()
    try {
      const r = await contract.getRound()
      const provider = useWalletStore.getState().provider
      if (!provider) throw new Error('Provider not available')
      const block = await provider.getBlock('latest')
      if (!block || block.timestamp === undefined) throw new Error('Failed to fetch block timestamp')
      const now = Number(block.timestamp)
      const minDraw = Number(r.minDrawTime)
      const maxDraw = Number(r.maxDrawTime)
      const hasPot = Number(r.totalPot) > 0
      const state = Number(r.state)
      // canDraw if within minDraw..maxDraw and pot > 0 and state is BETTING
      return state === RoundState.BETTING && now >= minDraw && now <= maxDraw && hasPot
    } catch (error: any) {
      throw new Error('Failed to check draw status: ' + (error.message || 'Unknown error'))
    }
  }

  /**
   * Check if current round can be refunded
   */
  async canRefund(): Promise<boolean> {
    // Determine refund eligibility based on round timing and state
    const contract = this.getContract()
    try {
      const r = await contract.getRound()
      const provider = useWalletStore.getState().provider
      if (!provider) throw new Error('Provider not available')
  const block = await provider.getBlock('latest')
  if (!block || block.timestamp === undefined) throw new Error('Failed to fetch block timestamp')
  const now = Number(block.timestamp)
  const maxDraw = Number(r.maxDrawTime)
  const state = Number(r.state)
  // canRefund if now > maxDraw and state is BETTING
  return state === RoundState.BETTING && now > maxDraw
    } catch (error: any) {
      throw new Error('Failed to check refund status: ' + (error.message || 'Unknown error'))
    }
  }

  /**
   * Get current round timing information
   */
  async getRoundTiming(): Promise<RoundTiming> {
    const contract = this.getContract()

    try {
      const r = await contract.getRound()
      const provider = useWalletStore.getState().provider
      if (!provider) throw new Error('Provider not available')
  const block = await provider.getBlock('latest')
  if (!block || block.timestamp === undefined) throw new Error('Failed to fetch block timestamp')
  const now = Number(block.timestamp)
      return {
        startTime: Number(r.startTime),
        endTime: Number(r.endTime),
        minDrawTime: Number(r.minDrawTime),
        maxDrawTime: Number(r.maxDrawTime),
        currentTime: now
      }
    } catch (error: any) {
      throw new Error('Failed to get round timing: ' + (error.message || 'Unknown error'))
    }
  }

  /**
   * Get current round ID
   */
  async getCurrentRoundId(): Promise<number> {
    const contract = this.getContract()

    try {
      const round = await contract.getRound()
      return Number(round.roundId)
    } catch (error: any) {
      throw new Error('Failed to get current round ID: ' + (error.message || 'Unknown error'))
    }
  }

  /**
   * Get minimum bet amount
   */
  async getMinBetAmount(): Promise<string> {
    const contract = this.getContract()

    try {
      const minBet = await contract.minBetAmount()
      return ethers.formatEther(minBet)
    } catch (error: any) {
      throw new Error('Failed to get minimum bet amount: ' + (error.message || 'Unknown error'))
    }
  }

  /**
   * Refund expired round (public function)
   */
  async refundExpiredRound(): Promise<string> {
    const contract = this.getContract()
    const { signer } = useWalletStore.getState()

    if (!signer) {
      throw new Error('Wallet not connected')
    }

    try {
      const tx = await contract.refundExpiredRound()
      const receipt = await tx.wait()
      return receipt.hash
    } catch (error: any) {
      if (error.code === 4001) {
        throw new Error('Transaction was rejected by user')
      } else if (error.message.includes('revert')) {
        const reason = error.message.match(/revert (.+)/)?.[1] || 'Transaction failed'
        throw new Error(reason)
      } else {
        throw new Error('Transaction failed: ' + (error.message || 'Unknown error'))
      }
    }
  }
/**
   * Get current round information
   */
  /**
   * Get current round information.
   *
   * If `contractAddress` and `rpcUrl` are provided, this will perform a read-only
   * RPC call (like `getContractConfig`) so it doesn't require a connected wallet.
   * Otherwise it falls back to using the wallet/provider via `getContract()`.
   */
  async getRound(): Promise<LotteryRound> {
    const contractAddress = this.contractAddress
    const rpcUrl = this.rpcUrl
    const chainId = this.chainId

    if (!contractAddress) throw new Error('Contract address not configured for getRound')
    if (!rpcUrl) throw new Error('RPC URL not configured for getRound')

    try {
      const abi = await this.loadAbi()
      const provider = new ethers.JsonRpcProvider(rpcUrl, chainId ? Number(chainId) : undefined)
      const contract = new ethers.Contract(contractAddress, abi, provider)
      const result = await contract.getRound()

      return {
        roundId: Number(result.roundId),
        startTime: Number(result.startTime),
        endTime: Number(result.endTime),
        minDrawTime: Number(result.minDrawTime),
        maxDrawTime: Number(result.maxDrawTime),
        totalPot: ethers.formatEther(result.totalPot),
        participantCount: Number(result.participantCount),
        winner: result.winner,
        publisherCommission: ethers.formatEther(result.publisherCommission),
        sparsityCommission: ethers.formatEther(result.sparsityCommission),
        winnerPrize: ethers.formatEther(result.winnerPrize),
        state: result.state as RoundState
      }
    } catch (error: any) {
      throw new Error('Failed to get round information: ' + (error.message || 'Unknown error'))
    }
  }

  /**
   * Get contract configuration using getConfig()
   */
  async getContractConfig(): Promise<{
    publisherAddr: string
    sparsityAddr: string
    operatorAddr: string
    publisherCommission: string
    sparsityCommission: string
    minBet: string
    bettingDur: string
    minDrawDelay: string
    maxDrawDelay: string
    minEndTimeExt: string
    minPart: string
    sparsityIsSet: boolean
  }> {
    const contractAddress = this.contractAddress
    const rpcUrl = this.rpcUrl
    const chainId = this.chainId

    if (!contractAddress) throw new Error('Contract address not configured for getContractConfig')
    if (!rpcUrl) throw new Error('RPC URL not configured for getContractConfig')

    try {
      // Load ABI and create read-only provider for this call
      const abi = await this.loadAbi()
      const provider = new ethers.JsonRpcProvider(rpcUrl, chainId ? Number(chainId) : undefined)
      const contract = new ethers.Contract(contractAddress, abi, provider)
      const cfg = await contract.getConfig()

      // getConfig() returns 11 values in this order:
      // 0 publisherAddr, 1 sparsityAddr, 2 operatorAddr,
      // 3 publisherCommission, 4 sparsityCommission,
      // 5 minBet, 6 bettingDur, 7 minDrawDelay, 8 maxDrawDelay,
      // 9 minEndTimeExt, 10 minPart (sparsityIsSet removed)
      const sparsityAddr = cfg.sparsityAddr ?? cfg[1]
      const sparsityIsSet = sparsityAddr !== "0x0000000000000000000000000000000000000000"
      
      return {
        publisherAddr: cfg.publisherAddr ?? cfg[0],
        sparsityAddr: sparsityAddr,
        operatorAddr: cfg.operatorAddr ?? cfg[2],
        publisherCommission: cfg.publisherCommission?.toString?.() ?? String(cfg[3]),
        sparsityCommission: cfg.sparsityCommission?.toString?.() ?? String(cfg[4]),
        minBet: cfg.minBet?.toString?.() ?? String(cfg[5]),
        bettingDur: cfg.bettingDur?.toString?.() ?? String(cfg[6]),
        minDrawDelay: cfg.minDrawDelay?.toString?.() ?? String(cfg[7]),
        maxDrawDelay: cfg.maxDrawDelay?.toString?.() ?? String(cfg[8]),
        minEndTimeExt: cfg.minEndTimeExt?.toString?.() ?? String(cfg[9]),
        minPart: cfg.minPart?.toString?.() ?? String(cfg[10]),
        sparsityIsSet: sparsityIsSet
      }
    } catch (error: any) {
      throw new Error('Failed to load contract config: ' + (error.message || 'Unknown error'))
    }
  }

  /**
   * Subscribe to contract events
   */
  subscribeToEvents(callbacks: {
    onRoundCreated?: (roundId: number, startTime: number, endTime: number, minDrawTime: number, maxDrawTime: number) => void
    onBetPlaced?: (roundId: number, player: string, amount: string, newTotal: string, timestamp: number) => void
    onEndTimeExtended?: (roundId: number, oldEndTime: number, newEndTime: number) => void
    onRoundStateChanged?: (roundId: number, oldState: RoundState, newState: RoundState) => void
    onRoundCompleted?: (roundId: number, winner: string, totalPot: string, winnerPrize: string, publisherCommission: string, sparsityCommission: string, randomSeed: string) => void
    onRoundRefunded?: (roundId: number, totalRefunded: string, participantCount: number, reason: string) => void
    onMinBetAmountUpdated?: (oldAmount: string, newAmount: string) => void
    onSparsitySet?: (sparsity: string) => void
    onOperatorUpdated?: (oldOperator: string, newOperator: string) => void
  }, contractAddress?: string) {
    const contract = this.getContract(contractAddress)

    if (callbacks.onRoundCreated) {
      contract.on('RoundCreated', (roundId, startTime, endTime, minDrawTime, maxDrawTime) => {
        callbacks.onRoundCreated!(Number(roundId), Number(startTime), Number(endTime), Number(minDrawTime), Number(maxDrawTime))
      })
    }

    if (callbacks.onBetPlaced) {
      contract.on('BetPlaced', (roundId, player, amount, newTotal, timestamp) => {
        callbacks.onBetPlaced!(Number(roundId), player, ethers.formatEther(amount), ethers.formatEther(newTotal), Number(timestamp))
      })
    }

    if (callbacks.onEndTimeExtended) {
      contract.on('EndTimeExtended', (roundId, oldEndTime, newEndTime) => {
        callbacks.onEndTimeExtended!(Number(roundId), Number(oldEndTime), Number(newEndTime))
      })
    }

    if (callbacks.onRoundStateChanged) {
      contract.on('RoundStateChanged', (roundId, oldState, newState) => {
        callbacks.onRoundStateChanged!(Number(roundId), oldState as RoundState, newState as RoundState)
      })
    }

    if (callbacks.onRoundCompleted) {
      contract.on('RoundCompleted', (roundId, winner, totalPot, winnerPrize, publisherCommission, sparsityCommission, randomSeed) => {
        callbacks.onRoundCompleted!(
          Number(roundId),
          winner,
          ethers.formatEther(totalPot),
          ethers.formatEther(winnerPrize),
          ethers.formatEther(publisherCommission),
          ethers.formatEther(sparsityCommission),
          randomSeed.toString()
        )
      })
    }

    if (callbacks.onRoundRefunded) {
      contract.on('RoundRefunded', (roundId, totalRefunded, participantCount, reason) => {
        callbacks.onRoundRefunded!(Number(roundId), ethers.formatEther(totalRefunded), Number(participantCount), reason)
      })
    }

    if (callbacks.onMinBetAmountUpdated) {
      contract.on('MinBetAmountUpdated', (oldAmount, newAmount) => {
        callbacks.onMinBetAmountUpdated!(ethers.formatEther(oldAmount), ethers.formatEther(newAmount))
      })
    }

    if (callbacks.onSparsitySet) {
      contract.on('SparsitySet', (sparsity) => {
        callbacks.onSparsitySet!(sparsity)
      })
    }

    if (callbacks.onOperatorUpdated) {
      contract.on('OperatorUpdated', (oldOperator, newOperator) => {
        callbacks.onOperatorUpdated!(oldOperator, newOperator)
      })
    }

    // Return cleanup function
    return () => {
      contract.removeAllListeners()
    }
  }
}

export const contractService = new ContractService()

// Convenience wrapper to allow importing the setter directly
export const setContractAddress = (address: string | null) => contractService.setContractAddress(address)
export const hasValidContractAddress = () => contractService.hasValidContractAddress()