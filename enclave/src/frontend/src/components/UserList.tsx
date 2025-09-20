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
  Divider,
  TextField,
  IconButton,
} from '@mui/material'
import { People, Person, ConfirmationNumber, Edit } from '@mui/icons-material'

import { getParticipants } from '../services/api'

interface Participant {
  address: string
  amount: string
  tickets: number
  timestamp: string
  nickname?: string
}

const UserList: React.FC = () => {
  const [participants, setParticipants] = useState<Participant[]>([])
  const [loading, setLoading] = useState(false)
  const [nicknames, setNicknames] = useState<Record<string, string>>({})

  const fetchParticipants = async () => {
    setLoading(true)
    try {
      const response = await getParticipants()
      const list = Array.isArray(response?.participants) ? response.participants : []
      setParticipants(list)
    } catch (error) {
      console.error('Error fetching participants:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchParticipants()
    
  // Load nicknames from local storage
    const savedNicknames = localStorage.getItem('userNicknames')
    if (savedNicknames) {
      setNicknames(JSON.parse(savedNicknames))
    }
    
    // Refresh participants every 10 seconds
    const interval = setInterval(fetchParticipants, 10000)
    return () => clearInterval(interval)
  }, [])

  const formatAddress = (address: string): string => {
    return `${address.slice(0, 6)}...${address.slice(-4)}`
  }

  const formatTime = (timestamp: string): string => {
    const date = new Date(timestamp)
    return date.toLocaleTimeString()
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

  const getTotalTickets = (): number => {
    return participants.reduce((total, participant) => total + participant.tickets, 0)
  }

  const getWinChance = (tickets: number): string => {
    const total = getTotalTickets()
    if (total === 0) return '0%'
    return ((tickets / total) * 100).toFixed(1) + '%'
  }

  const getNickname = (address: string): string => {
    return nicknames[address] || `User ${address.slice(-4)}`
  }

  const safeParticipants = Array.isArray(participants) ? participants : []
  const count = safeParticipants.length

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', p: 1 }}>
      <Box display="flex" alignItems="center" mb={1} justifyContent="center">
        <People sx={{ mr: 1, color: 'white' }} />
        <Typography variant="subtitle1" sx={{ color: 'white' }}>
          Participants ({count})
        </Typography>
      </Box>

      {count === 0 ? (
        <Box 
          display="flex" 
          flexDirection="column" 
          alignItems="center" 
          justifyContent="center" 
          flex={1}
          sx={{ color: 'rgba(255, 255, 255, 0.7)' }}
        >
          <Person sx={{ fontSize: 40, mb: 1 }} />
          <Typography variant="body2" textAlign="center">
            No participants yet
          </Typography>
          <Typography variant="caption">
            Place your first bet to join!
          </Typography>
        </Box>
      ) : (
        <Box flex={1} overflow="hidden">
          <List sx={{ overflow: 'auto', maxHeight: '100%', p: 0 }}>
            {safeParticipants.map((participant, index) => (
              <React.Fragment key={participant.address}>
                <ListItem sx={{ px: 1, py: 0.5 }}>
                  <ListItemIcon sx={{ minWidth: 40 }}>
                    <Avatar 
                      sx={{ 
                        bgcolor: getAvatarColor(participant.address),
                        width: 28, 
                        height: 28,
                        fontSize: '0.75rem'
                      }}
                    >
                      {participant.address.slice(2, 4).toUpperCase()}
                    </Avatar>
                  </ListItemIcon>
                  <ListItemText
                    primary={
                      <Typography variant="body2" sx={{ color: 'white', fontWeight: 'bold' }}>
                        {getNickname(participant.address)}
                      </Typography>
                    }
                    secondary={
                      <Box>
                        <Typography variant="caption" sx={{ color: 'rgba(255, 255, 255, 0.8)' }}>
                          {formatAddress(participant.address)}
                        </Typography>
                        <br />
                        <Box display="flex" alignItems="center" gap={0.5} mt={0.5}>
                          <Chip
                            label={`${participant.amount} ETH`}
                            size="small"
                            sx={{ 
                              height: 20, 
                              fontSize: '0.7rem',
                              bgcolor: 'rgba(255, 255, 255, 0.2)',
                              color: 'white'
                            }}
                          />
                          <Chip
                            icon={<ConfirmationNumber sx={{ fontSize: '0.7rem !important' }} />}
                            label={`${participant.tickets} tickets`}
                            size="small"
                            sx={{ 
                              height: 20, 
                              fontSize: '0.7rem',
                              bgcolor: 'rgba(76, 175, 80, 0.3)',
                              color: 'white'
                            }}
                          />
                        </Box>
                        <Typography variant="caption" sx={{ color: 'rgba(255, 255, 255, 0.6)' }}>
                          Win chance: {getWinChance(participant.tickets)}
                        </Typography>
                      </Box>
                    }
                  />
                </ListItem>
                {index < count - 1 && (
                  <Divider sx={{ borderColor: 'rgba(255, 255, 255, 0.2)' }} />
                )}
              </React.Fragment>
            ))}
          </List>
        </Box>
      )}

      {count > 0 && (
        <Box mt={1} pt={1} sx={{ borderTop: '1px solid rgba(255, 255, 255, 0.2)' }}>
          <Typography variant="caption" sx={{ color: 'rgba(255, 255, 255, 0.8)' }} textAlign="center">
            Total: {getTotalTickets()} tickets
          </Typography>
        </Box>
      )}
    </Box>
  )
}

export default UserList