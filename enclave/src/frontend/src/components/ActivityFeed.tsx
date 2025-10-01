import React, { useEffect, useState } from 'react'
import {
  Typography,
  Box,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Avatar,
  Chip,
} from '@mui/material'
import { 
  Notifications, 
  PersonAdd, 
  Casino, 
  EmojiEvents,
  AccessTime,
  Schedule
} from '@mui/icons-material'

import { getActivities } from '../services/api'

type ActivityType =
  | 'BetPlaced'
  | 'RoundCompleted'
  | 'RoundRefunded'
  | 'RoundCreated'
  | 'other'

interface Activity {
  activity_id: string
  user_address: string
  activity_type: ActivityType
  details: Record<string, any>
  message?: string
  severity?: string
  timestamp: string
}

const ActivityFeed: React.FC = () => {
  const [activities, setActivities] = useState<Activity[]>([])
  const [loading, setLoading] = useState(false)
  const [systemMessages, setSystemMessages] = useState<Array<{id: string, message: string, timestamp: Date}>>([])

  const fetchActivities = async () => {
    setLoading(true)
    try {
      const response = await getActivities()
      const list: Activity[] = Array.isArray(response?.activities) ? response.activities : []
      setActivities(list)
    } catch (error) {
      console.error('Error fetching activities:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchActivities()
    
    // Refresh activities every 5 seconds
    const interval = setInterval(fetchActivities, 2000)
    return () => clearInterval(interval)
  }, [])

  // systemMessages can be pushed manually by other UI interactions if needed.

  const formatAddress = (address: string): string => {
    return `${address.slice(0, 6)}...${address.slice(-4)}`
  }

  const formatTime = (timestamp: string | Date): string => {
    const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffSecs = Math.floor(diffMs / 1000)
    const diffMins = Math.floor(diffSecs / 60)

    if (diffSecs < 60) {
  return 'Just now'
    } else if (diffMins < 60) {
  return `${diffMins} minutes ago`
    } else {
      return date.toLocaleTimeString().slice(0, 5)
    }
  }

  const getActivityIcon = (type: ActivityType) => {
    switch (type) {
      case 'BetPlaced':
        return <Casino />
      case 'RoundCompleted':
        return <EmojiEvents />
      case 'RoundRefunded':
        return <EmojiEvents />
      case 'RoundCreated':
        return <Notifications />
      default:
        return <AccessTime />
    }
  }

  const getActivityColor = (type: ActivityType) => {
    switch (type) {
      case 'BetPlaced':
        return '#ff9800'
      case 'RoundCompleted':
        return '#4caf50'
      case 'RoundRefunded':
        return '#f44336'
      case 'RoundCreated':
        return '#03a9f4'
      default:
        return '#9e9e9e'
    }
  }

  const getActivityMessage = (activity: Activity): string => {
  const type = (activity.activity_type as ActivityType) ?? 'other'
  const details = activity.details || {}
  const user = activity.user_address || ''
  const address = user ? formatAddress(String(user)) : 'unknown'

    const weiToEth = (wei: any) => {
      try {
        const n = typeof wei === 'string' ? parseFloat(wei) : Number(wei)
        if (Number.isNaN(n)) return String(wei)
        return (n / 1e18).toFixed(4)
      } catch (e) {
        return String(wei)
      }
    }

    switch (type) {
      case 'BetPlaced': {
        const player = details.player || activity.user_address || ''
        const amt = details.amount || details.amountWei || details.totalAmountWei || 0
        return `💰 ${formatAddress(String(player || address))} placed ${weiToEth(amt)} ETH`
      }
      case 'RoundCompleted': {
        const winner = details.winner || activity.user_address || ''
        const amt = details.winnerPrize || details.totalPotWei || details.totalPot || 0
        return `🎉 ${formatAddress(String(winner || address))} won ${weiToEth(amt)} ETH!`
      }
      case 'RoundRefunded': {
        const rid = details.roundId
        const refunded = details.totalRefundedWei || details.totalRefunded || 0
        return `↩️ Round ${rid} refunded ${weiToEth(refunded)} ETH`
      }
      case 'RoundCreated': {
        const rid = details.roundId
        return `🔔 Round ${rid} created`
      }
      default:
        // For 'other' and any unexpected types, prefer server message or a generic text.
        return activity.message ? activity.message : `${address} performed ${String(type)}`
    }
  }

  const getAvatarColor = (address: string): string => {
    const colors = [
      '#f44336', '#e91e63', '#9c27b0', '#673ab7',
      '#3f51b5', '#2196f3', '#03a9f4', '#00bcd4',
      '#009688', '#4caf50', '#8bc34a', '#cddc39',
      '#ffeb3b', '#ffc107', '#ff9800', '#ff5722'
    ]
    const index = parseInt(address.slice(-2), 16) % colors.length
    return colors[index]
  }

  // Merge system messages (including derived persistent messages) and user activities
  const safeActivities = Array.isArray(activities) ? activities : []

  // No derived persistent messages; system messages are user-driven or server-provided.
  const derivedSystemMessages: Array<{id: string, message: string, timestamp: Date}> = []

  // Combine derived messages with ephemeral systemMessages and deduplicate by message text
  const combinedSystem = [...derivedSystemMessages, ...systemMessages]
  const seen = new Set<string>()
  const uniqueSystem = combinedSystem.filter(s => {
    if (seen.has(s.message)) return false
    seen.add(s.message)
    return true
  })

  const allMessages = [
    ...uniqueSystem.map(msg => ({
      id: msg.id,
      type: 'other',
      message: msg.message,
      timestamp: msg.timestamp,
      isSystem: true
    })),
    ...safeActivities.map(activity => ({
      id: activity.activity_id,
      type: activity.activity_type,
      // Prefer server-provided message when present; otherwise fall back to client-formatted text
      message: activity.message ? activity.message : getActivityMessage(activity as Activity),
      timestamp: new Date(activity.timestamp),
      activity,
      isSystem: false,
      severity: activity.severity ?? 'info',
    }))
  ].sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: '50%',
        overflowX: 'hidden',
        overflowY: 'auto',
        '&::-webkit-scrollbar': {
          width: '6px',
        },
        '&::-webkit-scrollbar-thumb': {
          backgroundColor: 'rgba(255, 255, 255, 0.3)',
          borderRadius: '3px',
        }
      }}
    >
      <Box display="flex" alignItems="center" mb={1} justifyContent="center">
        <Notifications sx={{ mr: 1, color: 'white' }} />
        <Typography variant="subtitle1" sx={{ color: 'white' }}>
          Live Feed
        </Typography>
        {allMessages.length > 0 && (
          <Chip 
            label="LIVE" 
            size="small" 
            sx={{ 
              ml: 1,
              bgcolor: 'rgba(76, 175, 80, 0.8)',
              color: 'white',
              animation: 'pulse 2s infinite'
            }}
          />
        )}
      </Box>

      {allMessages.length === 0 ? (
        <Box 
          display="flex" 
          flexDirection="column" 
          alignItems="center" 
          justifyContent="center" 
          flex={1}
          sx={{ color: 'rgba(255, 255, 255, 0.7)' }}
        >
          <Notifications sx={{ fontSize: 40, mb: 1 }} />
          <Typography variant="body2" textAlign="center">
            No activity yet
          </Typography>
          <Typography variant="caption">
            Live updates will appear here
          </Typography>
        </Box>
      ) : (
        <Box
          sx={{
            flexGrow: 1,
            background: 'rgba(0, 0, 0, 0.2)',
            borderRadius: 1,
            border: '1px solid rgba(255, 255, 255, 0.1)'
          }}
        >
          <List sx={{ p: 0.5 }}>
            {allMessages.map((message) => (
              <ListItem key={message.id} sx={{ px: 1, py: 0.5 }}>
                <ListItemIcon sx={{ minWidth: 35 }}>
                  <Avatar 
                    sx={{ 
                      bgcolor: message.isSystem ? getActivityColor('other') : getActivityColor((message.type as ActivityType) ?? 'other'),
                      width: 24, 
                      height: 24,
                      fontSize: '0.8rem'
                    }}
                  >
                    {getActivityIcon(message.isSystem ? 'other' : (message.type as ActivityType) ?? 'other')}
                  </Avatar>
                </ListItemIcon>
                <ListItemText
                  primary={
                    <Typography 
                      variant="body2" 
                      sx={{ 
                        color: 'white', 
                        fontSize: '0.85rem',
                        fontWeight: message.isSystem ? 'bold' : 'normal'
                      }}
                    >
                      {message.message}
                    </Typography>
                  }
                  secondary={
                    <Typography variant="caption" sx={{ color: 'rgba(255, 255, 255, 0.6)' }}>
                      {formatTime(message.timestamp)}
                    </Typography>
                  }
                  primaryTypographyProps={{ component: 'div' }}
                  secondaryTypographyProps={{ component: 'div' }}
                />
              </ListItem>
            ))}
          </List>
        </Box>
      )}

      <style>
        {`
          @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.7; }
            100% { opacity: 1; }
          }
        `}
      </style>
    </Box>
  )
}

export default ActivityFeed