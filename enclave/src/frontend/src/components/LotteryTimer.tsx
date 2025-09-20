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
  const { currentDraw } = useLotteryStore()
  const [timeRemaining, setTimeRemaining] = useState<TimeRemaining>({ hours: 0, minutes: 0, seconds: 0 })
  const [bettingTimeRemaining, setBettingTimeRemaining] = useState<TimeRemaining>({ hours: 0, minutes: 0, seconds: 0 })

  useEffect(() => {
    if (!currentDraw) return

    const updateTimers = () => {
      const now = new Date().getTime()
      const drawTime = new Date(currentDraw.draw_time).getTime()
      const endTime = new Date(currentDraw.end_time).getTime()

      // Calculate time remaining until draw
      const drawDiff = Math.max(0, drawTime - now)
      const drawHours = Math.floor(drawDiff / (1000 * 60 * 60))
      const drawMinutes = Math.floor((drawDiff % (1000 * 60 * 60)) / (1000 * 60))
      const drawSeconds = Math.floor((drawDiff % (1000 * 60)) / 1000)
      setTimeRemaining({ hours: drawHours, minutes: drawMinutes, seconds: drawSeconds })

      // Calculate time remaining for betting
      const bettingDiff = Math.max(0, endTime - now)
      const bettingHours = Math.floor(bettingDiff / (1000 * 60 * 60))
      const bettingMinutes = Math.floor((bettingDiff % (1000 * 60 * 60)) / (1000 * 60))
      const bettingSeconds = Math.floor((bettingDiff % (1000 * 60)) / 1000)
      setBettingTimeRemaining({ hours: bettingHours, minutes: bettingMinutes, seconds: bettingSeconds })
    }

    updateTimers()
    const interval = setInterval(updateTimers, 1000)

    return () => clearInterval(interval)
  }, [currentDraw])

  if (!currentDraw) {
    return (
      <Box sx={{ p: 2, textAlign: 'center', color: 'white' }}>
  <Typography variant="body1">Loading lottery information...</Typography>
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
      case 'betting': return 'Betting Open'
      case 'closed': return 'Closed'
      case 'drawn': return 'Drawn'
      default: return 'Unknown'
    }
  }

  const getTotalTimeSeconds = () => {
    if (!currentDraw) return 0
    const start = new Date(currentDraw.start_time).getTime()
    const end = new Date(currentDraw.draw_time).getTime()
    return (end - start) / 1000
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
    <Box sx={{ p: 1.5, mb: 2 }}>
  {/* Title row */}
      <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
        <Box display="flex" alignItems="center">
          <Timer sx={{ mr: 1, color: 'white' }} />
          <Typography variant="h6" sx={{ color: 'white', fontWeight: 'bold' }}>
            Next Draw
          </Typography>
        </Box>
        <Chip 
          label={getStatusText(currentDraw.status)} 
          size="small"
          sx={{ 
            bgcolor: getStatusColor(currentDraw.status),
            color: 'white',
            fontWeight: 'bold'
          }}
        />
      </Box>
      
  {/* Main info row */}
      <Grid container spacing={2} alignItems="center" mb={2}>
        <Grid item xs={4}>
          <Box textAlign="center">
            <Schedule sx={{ color: 'white', mb: 0.5, fontSize: '1.2rem' }} />
            <Typography variant="h5" sx={{ color: '#ffeb3b', fontWeight: 'bold', fontFamily: 'monospace' }}>
              {formatTime(timeRemaining)}
            </Typography>
            <Typography variant="caption" sx={{ color: 'rgba(255, 255, 255, 0.8)' }}>
              Time until draw
            </Typography>
          </Box>
        </Grid>

        <Grid item xs={4}>
          <Box textAlign="center">
            <AttachMoney sx={{ color: 'white', mb: 0.5, fontSize: '1.2rem' }} />
            <Typography variant="h5" sx={{ color: '#4caf50', fontWeight: 'bold' }}>
              {currentDraw.total_pot}
            </Typography>
            <Typography variant="caption" sx={{ color: 'rgba(255, 255, 255, 0.8)' }}>
              Prize Pool (ETH)
            </Typography>
          </Box>
        </Grid>

        <Grid item xs={4}>
          <Box textAlign="center">
            <People sx={{ color: 'white', mb: 0.5, fontSize: '1.2rem' }} />
            <Typography variant="h5" sx={{ color: '#2196f3', fontWeight: 'bold' }}>
              {currentDraw.participants}
            </Typography>
            <Typography variant="caption" sx={{ color: 'rgba(255, 255, 255, 0.8)' }}>
              Participants
            </Typography>
          </Box>
        </Grid>
      </Grid>

  {/* Betting cutoff reminder */}
      {currentDraw.status === 'betting' && bettingTimeRemaining.hours === 0 && bettingTimeRemaining.minutes < 10 && (
        <Box mb={2} sx={{ 
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