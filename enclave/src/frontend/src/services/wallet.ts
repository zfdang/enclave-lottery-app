import { create } from 'zustand'
import { ethers } from 'ethers'

interface WalletState {
  isConnected: boolean
  address: string | null
  balance: string | null
  isConnecting: boolean
  provider: ethers.BrowserProvider | null
  signer: ethers.Signer | null
  connect: () => Promise<void>
  disconnect: () => void
  sendTransaction: (tx: { to: string; value: string }) => Promise<string>
  updateBalance: () => Promise<void>
}

declare global {
  interface Window {
    ethereum?: any
  }
}

export const useWalletStore = create<WalletState>((set, get) => ({
  isConnected: false,
  address: null,
  balance: null,
  isConnecting: false,
  provider: null,
  signer: null,

  connect: async () => {
    if (!window.ethereum) {
      throw new Error('MetaMask is not installed. Please install MetaMask to continue.')
    }

    set({ isConnecting: true })

    try {
      // Request account access
      await window.ethereum.request({ method: 'eth_requestAccounts' })

      // Create provider and signer
      const provider = new ethers.BrowserProvider(window.ethereum)
      const signer = await provider.getSigner()
      const address = await signer.getAddress()

      // Get balance
      const balance = await provider.getBalance(address)
      const balanceInEth = ethers.formatEther(balance)

      set({
        isConnected: true,
        address,
        balance: balanceInEth,
        provider,
        signer,
        isConnecting: false,
      })

      // Listen for account changes
      window.ethereum.on('accountsChanged', (accounts: string[]) => {
        if (accounts.length === 0) {
          get().disconnect()
        } else {
          // Account changed, reconnect
          get().connect()
        }
      })

      // Listen for chain changes
      window.ethereum.on('chainChanged', () => {
        // Reload the page when chain changes
        window.location.reload()
      })

    } catch (error: any) {
      set({ isConnecting: false })
      if (error.code === 4001) {
        throw new Error('Please connect your MetaMask wallet to continue.')
      } else {
        throw new Error('Failed to connect to MetaMask. Please try again.')
      }
    }
  },

  disconnect: () => {
    set({
      isConnected: false,
      address: null,
      balance: null,
      provider: null,
      signer: null,
    })
  },

  sendTransaction: async (tx: { to: string; value: string }) => {
    const { signer } = get()
    if (!signer) {
      throw new Error('Wallet not connected')
    }

    try {
      const transaction = {
        to: tx.to,
        value: ethers.parseEther(tx.value),
      }

      const txResponse = await signer.sendTransaction(transaction)
      
      // Wait for transaction to be mined
      await txResponse.wait()
      
      // Update balance after transaction
      get().updateBalance()
      
      return txResponse.hash
    } catch (error: any) {
      if (error.code === 4001) {
        throw new Error('Transaction was rejected by user')
      } else {
        throw new Error('Transaction failed: ' + (error.message || 'Unknown error'))
      }
    }
  },

  updateBalance: async () => {
    const { provider, address } = get()
    if (!provider || !address) return

    try {
      const balance = await provider.getBalance(address)
      const balanceInEth = ethers.formatEther(balance)
      set({ balance: balanceInEth })
    } catch (error) {
      console.error('Failed to update balance:', error)
    }
  },
}))

// Auto-connect if previously connected
if (typeof window !== 'undefined' && window.ethereum) {
  try {
    const maybePromise = window.ethereum.request({ method: 'eth_accounts' })
    // Some environments may not fully implement EIP-1193; guard the result
    Promise.resolve(maybePromise)
      .then((accounts: unknown) => {
        if (Array.isArray(accounts) && accounts.length > 0) {
          useWalletStore.getState().connect().catch(console.error)
        }
      })
      .catch((err: any) => {
        console.warn('eth_accounts check failed:', err?.message || err)
      })
  } catch (err: any) {
    console.warn('eth_accounts request error:', err?.message || err)
  }
}