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
  AttachMoney,
  EmojiEvents,
  AccessTime,
  Transform,
  Replay,
  FiberNew
} from '@mui/icons-material'

import { getActivities } from '../services/api'
import { formatAddress, formatTime, generateAvatarColor } from '../utils/helpers'

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



  const ACTIVITY_VISUALS: Record<ActivityType, { icon: React.ReactNode; color: string }> = {
    BetPlaced: { icon: <AttachMoney />, color: '#ff9800' },
    RoundStateChanged: { icon: <Transform />, color: '#9575cd' },
    RoundCompleted: { icon: <EmojiEvents />, color: '#4caf50' },
    RoundRefunded: { icon: <Replay />, color: '#f44336' },
    RoundCreated: { icon: <FiberNew />, color: '#03a9f4' },
    other: { icon: <AccessTime />, color: '#9e9e9e' },
  }

  const resolveActivityVisual = (type: ActivityType) => ACTIVITY_VISUALS[type] ?? ACTIVITY_VISUALS.other

  const getActivityIcon = (type: ActivityType) => resolveActivityVisual(type).icon

  const getActivityColor = (type: ActivityType) => resolveActivityVisual(type).color




  return (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        p: 1,
        minHeight: 0
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
        <Box flex={1} overflow="hidden" sx={{ minHeight: 0 }}>
          <List sx={{ overflow: 'auto', height: '100%', p: 0 }}>
            {activities.map((activity) => (
              <ListItem key={activity.activity_id} sx={{ px: 1, py: 0.5 }}>
                <ListItemIcon sx={{ minWidth: 35 }}>
                  <Avatar 
                    sx={{ 
                      bgcolor: getActivityColor(activity.activity_type),
                      width: 24, 
                      height: 24,
                      fontSize: '0.8rem',
                      color: 'white'
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