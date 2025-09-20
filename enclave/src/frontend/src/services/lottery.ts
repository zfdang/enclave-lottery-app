import { create } from 'zustand'
import { getCurrentDraw } from './api'

interface CurrentDraw {
  draw_id: string
  start_time: string
  end_time: string
  draw_time: string
  status: string
  total_pot: string
  participants: number
  time_remaining: number
  betting_time_remaining: number
}

interface LotteryState {
  currentDraw: CurrentDraw | null
  loading: boolean
  error: string | null
  fetchCurrentDraw: () => Promise<void>
  setCurrentDraw: (draw: CurrentDraw | null) => void
}

export const useLotteryStore = create<LotteryState>((set, get) => ({
  currentDraw: null,
  loading: false,
  error: null,

  fetchCurrentDraw: async () => {
    set({ loading: true, error: null })
    
    try {
      const data = await getCurrentDraw()
      set({ currentDraw: data, loading: false })
    } catch (error: any) {
      set({ 
        error: error.message || 'Failed to fetch current draw',
        loading: false 
      })
    }
  },

  setCurrentDraw: (draw: CurrentDraw | null) => {
    set({ currentDraw: draw })
  },
}))

// Auto-fetch current draw every 30 seconds
if (typeof window !== 'undefined') {
  setInterval(() => {
    useLotteryStore.getState().fetchCurrentDraw()
  }, 30000)
}