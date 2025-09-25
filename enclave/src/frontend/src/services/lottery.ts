import { create } from 'zustand'
import { getCurrentDraw } from './api'

interface CurrentRound {
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

interface RoundStatusResponse {
  round: CurrentRound | null
  message?: string
  can_bet: boolean
  can_draw: boolean
  is_finished: boolean
  is_active: boolean
  betting_time_remaining: number
  draw_window_start: number
  draw_window_end: number
  current_time: number
}

interface LotteryState {
  currentRound: RoundStatusResponse | null
  loading: boolean
  error: string | null
  fetchCurrentDraw: () => Promise<void>
  setCurrentRound: (round: RoundStatusResponse | null) => void
}

export const useLotteryStore = create<LotteryState>((set, get) => ({
  currentRound: null,
  loading: false,
  error: null,

  fetchCurrentDraw: async () => {
    set({ loading: true, error: null })
    
    try {
      const data = await getCurrentDraw()
      set({ currentRound: data, loading: false, error: null })
    } catch (error: any) {
      console.warn('Backend connection failed:', error.message)
      set({ 
        error: error.message || 'Failed to fetch current round status',
        loading: false 
      })
      // Don't throw error to prevent component crashes
    }
  },

  setCurrentRound: (round: RoundStatusResponse | null) => {
    set({ currentRound: round })
  },
}))

// Auto-fetch current draw every 30 seconds
if (typeof window !== 'undefined') {
  setInterval(() => {
    useLotteryStore.getState().fetchCurrentDraw()
  }, 30000)
}