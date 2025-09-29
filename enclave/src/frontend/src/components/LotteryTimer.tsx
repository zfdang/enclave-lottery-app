import React, { useEffect, useState } from 'react'
import {
  Typography,
  Box,
  LinearProgress,
  Chip,
  Grid,
} from '@mui/material'
import { Timer, People, AttachMoney, Schedule } from '@mui/icons-material'

import { useLotteryStore } from '../services/lottery'

interface TimeRemaining {
  hours: number
  minutes: number
  seconds: number
}

const LotteryTimer: React.FC = () => {
  const { roundStatus, loading, error } = useLotteryStore()
  const [timeRemaining, setTimeRemaining] = useState<TimeRemaining>({ hours: 0, minutes: 0, seconds: 0 })
  const [bettingTimeRemaining, setBettingTimeRemaining] = useState<TimeRemaining>({ hours: 0, minutes: 0, seconds: 0 })

  // Robust UTC parser: accepts ISO strings or numeric timestamps (seconds or ms).
  const parseUtcMillis = (iso: string | number | undefined | null): number => {
    if (iso === undefined || iso === null) return NaN
    if (typeof iso === 'number') {
      // Normalize seconds -> ms
      return iso > 1e12 ? iso : iso * 1000
    }
    const s = String(iso)
    const hasTZ = /[Zz]|[+-]\d{2}:\d{2}$/.test(s)
    return new Date(hasTZ ? s : `${s}Z`).getTime()
  }

  useEffect(() => {
    // Poll backend every FETCH_POLL_MS for round status, and update local timers
    // once per second by reading the latest store state. Reading the store
    // inside the timer prevents the effect from re-running on each store update
    // (which previously caused an immediate refetch loop).
    const FETCH_POLL_MS = 5000
    const fetchNow = async () => {
      try {
        await useLotteryStore.getState().fetchRoundStatus()
      } catch (e) {
        // fetchRoundStatus handles its own errors
      }
    }

    // Start the periodic fetch and timer-driven UI updates
    fetchNow()
    const poll = setInterval(fetchNow, FETCH_POLL_MS)

    const updateTimers = () => {
      const current = useLotteryStore.getState().roundStatus
      if (!current) return
      const now = Date.now()
      const drawTime = parseUtcMillis((current as any).min_draw_time)
      const endTime = parseUtcMillis((current as any).end_time)

      // Calculate time remaining until draw
      const drawDiffRaw = drawTime - now
      const drawDiff = Number.isNaN(drawDiffRaw) ? 0 : Math.max(0, drawDiffRaw)
      const drawHours = Math.floor(drawDiff / (1000 * 60 * 60))
      const drawMinutes = Math.floor((drawDiff % (1000 * 60 * 60)) / (1000 * 60))
      const drawSeconds = Math.floor((drawDiff % (1000 * 60)) / 1000)
      setTimeRemaining({ hours: drawHours, minutes: drawMinutes, seconds: drawSeconds })

      // Calculate time remaining for betting
      const bettingDiffRaw = endTime - now
      const bettingDiff = Number.isNaN(bettingDiffRaw) ? 0 : Math.max(0, bettingDiffRaw)
      const bettingHours = Math.floor(bettingDiff / (1000 * 60 * 60))
      const bettingMinutes = Math.floor((bettingDiff % (1000 * 60 * 60)) / (1000 * 60))
      const bettingSeconds = Math.floor((bettingDiff % (1000 * 60)) / 1000)
      setBettingTimeRemaining({ hours: bettingHours, minutes: bettingMinutes, seconds: bettingSeconds })
    }

    updateTimers()
    const timer = setInterval(updateTimers, 1000)

    return () => {
      clearInterval(timer)
      clearInterval(poll)
    }
  }, [])

  if (!roundStatus) {
    return (
      <Box sx={{ p: 2, textAlign: 'center', color: 'white' }}>
        {loading ? (
          <Typography variant="body1">Loading lottery information...</Typography>
        ) : (
          <Typography variant="body1">No lottery data available</Typography>
        )}
      </Box>
    )
  }

  const formatTime = (time: TimeRemaining): string => {
    return `${time.hours.toString().padStart(2, '0')}:${time.minutes.toString().padStart(2, '0')}:${time.seconds.toString().padStart(2, '0')}`
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'betting': return 'rgba(76, 175, 80, 0.8)'
      case 'closed': return 'rgba(255, 152, 0, 0.8)'
      case 'drawn': return 'rgba(33, 150, 243, 0.8)'
      default: return 'rgba(158, 158, 158, 0.8)'
    }
  }

  const getStatusText = (status: string) => {
    switch (status) {
      case 'waiting': return 'Waiting'
      case 'betting': return 'Betting Open'
      case 'closed': return 'Closed'
      case 'drawn': return 'Drawn'
      default: return 'Unknown'
    }
  }

  const getTotalTimeSeconds = () => {
    if (!roundStatus) return 0
    const start = parseUtcMillis((roundStatus as any).start_time)
    const end = parseUtcMillis((roundStatus as any).max_draw_time ?? (roundStatus as any).end_time)
    const diff = end - start
    return Number.isNaN(diff) ? 0 : diff / 1000
  }

  const getRemainingTimeSeconds = () => {
    return timeRemaining.hours * 3600 + timeRemaining.minutes * 60 + timeRemaining.seconds
  }

  const getProgressValue = () => {
    const total = getTotalTimeSeconds()
    const remaining = getRemainingTimeSeconds()
    return total > 0 ? ((total - remaining) / total) * 100 : 0
  }

  return (
    <Box sx={{ p: 1, mb: 1 }}>
  {/* Title row */}
      <Box display="flex" alignItems="center" justifyContent="space-between" mb={1}>
        <Box display="flex" alignItems="center">
          <Timer sx={{ mr: 1, color: 'white' }} />
          <Typography variant="h6" sx={{ color: 'white', fontWeight: 'bold' }}>
            Next Draw
          </Typography>
        </Box>
        <Chip 
          label={getStatusText(roundStatus.state_name)} 
          size="small"
          sx={{ 
            bgcolor: getStatusColor(roundStatus.state_name),
            color: 'white',
            fontWeight: 'bold'
          }}
        />
      </Box>
      
  {/* Main info row */}
      <Grid container spacing={1} alignItems="center" mb={1}>
        <Grid item xs={4}>
          <Box textAlign="center">
            <Schedule sx={{ color: 'white', mb: 0.5, fontSize: '1rem' }} />
            <Typography variant="h6" sx={{ color: '#ffeb3b', fontWeight: 'bold', fontFamily: 'monospace' }}>
              {formatTime(timeRemaining)}
            </Typography>
            <Typography variant="caption" sx={{ color: 'rgba(255, 255, 255, 0.8)' }}>
              Time until draw
            </Typography>
          </Box>
        </Grid>

        <Grid item xs={4}>
          <Box textAlign="center">
            <AttachMoney sx={{ color: 'white', mb: 0.5, fontSize: '1rem' }} />
            <Typography variant="h6" sx={{ color: '#4caf50', fontWeight: 'bold' }}>
              {((roundStatus.total_pot ?? 0) / 1e18).toFixed(4)}
            </Typography>
            <Typography variant="caption" sx={{ color: 'rgba(255, 255, 255, 0.8)' }}>
              Prize Pool (ETH)
            </Typography>
          </Box>
        </Grid>

        <Grid item xs={4}>
          <Box textAlign="center">
            <People sx={{ color: 'white', mb: 0.5, fontSize: '1rem' }} />
            <Typography variant="h6" sx={{ color: '#2196f3', fontWeight: 'bold' }}>
              {roundStatus.participants}
            </Typography>
            <Typography variant="caption" sx={{ color: 'rgba(255, 255, 255, 0.8)' }}>
              Participants
            </Typography>
          </Box>
        </Grid>
      </Grid>

  {/* Betting cutoff reminder: only show when time until draw < minimum_interval_minutes */}
  {roundStatus.state_name === 'betting' && (() => {
        const minMin = (roundStatus as any).minimum_interval_minutes ?? 3
        const secsUntilDraw = timeRemaining.hours * 3600 + timeRemaining.minutes * 60 + timeRemaining.seconds
        return secsUntilDraw > 0 && secsUntilDraw < minMin * 60
      })() && (
        <Box mb={1} sx={{ 
          p: 1, 
          bgcolor: 'rgba(255, 152, 0, 0.2)', 
          border: '1px solid rgba(255, 152, 0, 0.5)',
          borderRadius: 1 
        }}>
          <Typography variant="body2" sx={{ color: '#ffb74d', fontWeight: 'bold', textAlign: 'center' }}>
            ⚠️ Betting closes in {formatTime(bettingTimeRemaining)}
          </Typography>
        </Box>
      )}

  {/* Progress bar */}
      <Box>
        <Box display="flex" justifyContent="space-between" mb={0.5}>
          <Typography variant="caption" sx={{ color: 'rgba(255, 255, 255, 0.8)' }}>
            Draw progress
          </Typography>
          <Typography variant="caption" sx={{ color: 'rgba(255, 255, 255, 0.8)' }}>
            {getProgressValue().toFixed(1)}%
          </Typography>
        </Box>
        <LinearProgress 
          variant="determinate" 
          value={getProgressValue()} 
          sx={{ 
            height: 6, 
            borderRadius: 3,
            bgcolor: 'rgba(255, 255, 255, 0.2)',
            '& .MuiLinearProgress-bar': {
              bgcolor: 'linear-gradient(90deg, #4caf50 0%, #81c784 100%)'
            }
          }}
        />
      </Box>
    </Box>
  )
}

export default LotteryTimer