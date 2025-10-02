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
  | 'RoundStateChanged'
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
  timestamp: number
}

const ActivityFeed: React.FC = () => {
  const [activities, setActivities] = useState<Activity[]>([])
  const [loading, setLoading] = useState(false)

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

  const formatAddress = (address: string): string => {
    return `${address.slice(0, 6)}...${address.slice(-4)}`
  }

  const formatTime = (timestamp: number | Date): string => {
    // Handle Unix timestamp (in seconds or milliseconds)
    let date: Date
    if (typeof timestamp === 'number') {
      // If timestamp is in seconds (< 10 digits), convert to milliseconds
      const ts = timestamp < 10000000000 ? timestamp * 1000 : timestamp
      date = new Date(ts)
    } else {
      date = timestamp
    }

    if (!date || Number.isNaN(date.getTime())) {
      return ''
    }

    // Format in user's local timezone and locale
    try {
      return new Intl.DateTimeFormat(undefined, {
        year: 'numeric',
        month: 'short',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        timeZoneName: 'short'
      }).format(date)
    } catch (error) {
      console.warn('Date formatting failed, using fallback:', error)
      return date.toLocaleString()
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

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        minHeight: '400px',
        maxHeight: '400px',
      }}
    >
      <Box display="flex" alignItems="center" mb={1} justifyContent="center" sx={{ flexShrink: 0 }}>
        <Notifications sx={{ mr: 1, color: 'white' }} />
        <Typography variant="subtitle1" sx={{ color: 'white' }}>
          Live Feed
        </Typography>
        {activities.length > 0 && (
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

      {activities.length === 0 ? (
        <Box 
          display="flex" 
          flexDirection="column" 
          alignItems="center" 
          justifyContent="center" 
          flex={1}
          sx={{ 
            color: 'rgba(255, 255, 255, 0.7)',
            minHeight: '300px'
          }}
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
            height: 0, // Force flex child to respect parent's height constraints
            background: 'rgba(0, 0, 0, 0.2)',
            borderRadius: 1,
            border: '1px solid rgba(255, 255, 255, 0.1)',
            overflowY: 'scroll',
            overflowX: 'hidden',
            '&::-webkit-scrollbar': {
              width: '8px',
            },
            '&::-webkit-scrollbar-track': {
              backgroundColor: 'rgba(255, 255, 255, 0.1)',
              borderRadius: '4px',
            },
            '&::-webkit-scrollbar-thumb': {
              backgroundColor: 'rgba(255, 255, 255, 0.3)',
              borderRadius: '4px',
              '&:hover': {
                backgroundColor: 'rgba(255, 255, 255, 0.5)',
              }
            }
          }}
        >
          <List sx={{ p: 1, pb: 4 }}>
            {activities.map((activity) => (
              <ListItem key={activity.activity_id} sx={{ px: 1, py: 0.5 }}>
                <ListItemIcon sx={{ minWidth: 35 }}>
                  <Avatar 
                    sx={{ 
                      bgcolor: getActivityColor(activity.activity_type),
                      width: 24, 
                      height: 24,
                      fontSize: '0.8rem'
                    }}
                  >
                    {getActivityIcon(activity.activity_type)}
                  </Avatar>
                </ListItemIcon>
                <ListItemText
                  primary={
                    <Typography 
                      variant="body2" 
                      sx={{ 
                        color: 'white', 
                        fontSize: '0.85rem'
                      }}
                    >
                      {activity.message || 'Activity'}
                    </Typography>
                  }
                  secondary={
                    <Typography variant="caption" sx={{ color: 'rgba(255, 255, 255, 0.6)' }}>
                      {formatTime(activity.timestamp)}
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