import { create } from 'zustand'
import { getRoundStatus } from './api'

interface RoundStatus {
  round_id: number
  state: number
  state_name: string
  start_time: number
  end_time: number
  min_draw_time: number
  max_draw_time: number
  total_pot: number
  participant_count: number
  participants: string[]
  winner: string | null
  publisher_commission: number
  sparsity_commission: number
  winner_prize: number
}

interface LotteryState {
  roundStatus: RoundStatus | null
  loading: boolean
  error: string | null
  fetchRoundStatus: () => Promise<void>
  setRoundStatus: (round: RoundStatus | null) => void
}

export const useLotteryStore = create<LotteryState>((set, get) => ({
  roundStatus: null,
  loading: false,
  error: null,

  fetchRoundStatus: async () => {
    set({ loading: true, error: null })
    
    try {
      const data = await getRoundStatus()
      set({ roundStatus: data, loading: false, error: null })
    } catch (error: any) {
      console.warn('Backend connection failed:', error.message)
      set({ 
        error: error.message || 'Failed to fetch current round status',
        loading: false 
      })
      // Don't throw error to prevent component crashes
    }
  },

  setRoundStatus: (round: RoundStatus | null) => {
    set({ roundStatus: round })
  },
}))