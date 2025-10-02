import { ethers, isAddress } from 'ethers'
import { useWalletStore } from './wallet'

// ABI is loaded via `loadAbi()`; do not embed a fallback ABI here.

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
  private contractAddress: string = ''
  private cachedAbi: any | null = null
  private rpcUrl: string
  private chainId: number | undefined
  minBetAmount: number | undefined //  minimum bet amount in gwei

  constructor() {
    // Get contract address from environment or config (Vite uses import.meta.env)
    this.contractAddress = import.meta.env.VITE_LOTTERY_CONTRACT_ADDRESS || ''
    this.rpcUrl = import.meta.env.VITE_RPC_URL || ''
    this.chainId = import.meta.env.VITE_CHAIN_ID ? Number(import.meta.env.VITE_CHAIN_ID) : undefined
    // console.log('ContractService initialized with address:', this.contractAddress + ', rpcUrl:', this.rpcUrl + ', chainId:', this.chainId)
  }

  /**
   * Set or update the configured contract address used by this service.
   * Passing a falsy value (null or empty string) will clear the configured address.
   */
  setContractAddress(address: string | null) {
    if (!address) {
      this.contractAddress = ''
      return
    }

    if (!isAddress(address)) {
      throw new Error('Invalid Ethereum address')
    }

    this.contractAddress = address
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

  /**
   * Place a bet on the current lottery round
   */
  async placeBet(betAmount: string): Promise<string> {
    const { signer } = useWalletStore.getState()

    if (!signer) {
      throw new Error('Wallet not connected')
    }

    if (!this.contractAddress) {
      throw new Error('Contract address not configured')
    }

    try {
      const betAmountWei = ethers.parseEther(betAmount)

      // Use cached ABI and the wallet signer to send the transaction
      const abi = await this.loadAbi()
      const signedContract = new ethers.Contract(this.contractAddress, abi, signer)
      const tx = await signedContract.placeBet({ value: betAmountWei })
      const receipt = await tx.wait()

      // Update wallet balance
      useWalletStore.getState().updateBalance()

      return receipt.hash
    } catch (error: any) {
      if (error.code === 4001) {
        throw new Error('Transaction was rejected by user')
      } else if (error.message && error.message.includes('revert')) {
        // Extract revert reason
        const reason = error.message.match(/revert (.+)/)?.[1] || 'Transaction failed'
        throw new Error(reason)
      } else {
        throw new Error('Transaction failed: ' + (error?.message || 'Unknown error'))
      }
    }
  }

    /**
   * Get minimum bet amount
   */
  async getMinBetAmount(): Promise<string> {
    // Return cached value if available
    if (this.minBetAmount !== undefined) {
      return String(this.minBetAmount)
    }
    const contractAddress = this.contractAddress
    const rpcUrl = this.rpcUrl
    const chainId = this.chainId

    if (!contractAddress) throw new Error('Contract address not configured for getMinBetAmount')
    if (!rpcUrl) throw new Error('RPC URL not configured for getMinBetAmount')

    try {
      const abi = await this.loadAbi()
      const provider = new ethers.JsonRpcProvider(rpcUrl, chainId ? Number(chainId) : undefined)
      const contract = new ethers.Contract(contractAddress, abi, provider)

      // Use the new dedicated getter on-chain for the minimum bet amount
      const minBetVal = await contract.getMinBetAmount()
      let minBetStr: string
      try {
        minBetStr = ethers.formatEther(minBetVal)
      } catch (e) {
        minBetStr = String(minBetVal)
      }

      // cache numeric value in ETH
      try { this.minBetAmount = Number(minBetStr) } catch (e) { /* ignore */ }
      return minBetStr
    } catch (error: any) {
      throw new Error('Failed to get minimum bet amount: ' + (error.message || 'Unknown error'))
    }
  }
  
  /**
   * Get current round information.
   *
   * If `contractAddress` and `rpcUrl` are provided, this will perform a read-only
   * RPC call (like `getContractConfig`) so it doesn't require a connected wallet.
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
      
      const minBetVal = cfg.minBet ?? cfg[5]
      let minBetStr: string
      try {
        // If minBetVal is a BigNumber-like, format it
        minBetStr = ethers.formatEther(minBetVal)
      } catch (e) {
        minBetStr = String(minBetVal)
      }

      // Cache numeric min bet in ETH
      try {
        this.minBetAmount = Number(minBetStr)
      } catch (e) {
        // ignore parse errors
      }

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


}
export const contractService = new ContractService()

// Convenience wrapper to allow importing the setter directly
export const setContractAddress = (address: string | null) => contractService.setContractAddress(address)
export const hasValidContractAddress = () => contractService.hasValidContractAddress()