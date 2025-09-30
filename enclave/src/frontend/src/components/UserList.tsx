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
} from '@mui/material'
import { People, Person, ConfirmationNumber } from '@mui/icons-material'

import { getParticipants } from '../services/api'

interface Participant {
  address: string
  // backend now provides aggregated fields:
  totalAmountWei: number
  // betCount removed from backend; it may be omitted
}

interface ParticipantsResponse {
  round_id: number | null
  round_state?: string
  participants: Participant[]
  total_participants: number
  total_bets: number
  // backend uses snake_case for aggregates
  total_amount_wei: number
  current_time: number
  message?: string
}

const UserList: React.FC = () => {
  const [participantsData, setParticipantsData] = useState<ParticipantsResponse | null>(null)
  const [loading, setLoading] = useState(false)

  const fetchParticipants = async () => {
    setLoading(true)
    try {
      const response = await getParticipants()
      setParticipantsData(response)
    } catch (error) {
      console.error('Error fetching participants:', error)
      setParticipantsData(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchParticipants()
    const interval = setInterval(fetchParticipants, 10000)
    return () => clearInterval(interval)
  }, [])

  const formatAddress = (address: string): string => {
    return address.slice(0, 6) + '...' + address.slice(-4)
  }

  const formatEth = (wei: number): string => {
    return (wei / 1e18).toFixed(4)
  }

  const getAvatarColor = (address: string): string => {
    // Expanded palette to reduce color collisions for many participants
    const colors = [
      '#f44336', '#e91e63', '#9c27b0', '#673ab7',
      '#3f51b5', '#2196f3', '#03a9f4', '#00bcd4',
      '#009688', '#4caf50', '#8bc34a', '#cddc39',
      '#ffeb3b', '#ffc107', '#ff9800', '#ff5722',
      '#795548', '#9e9e9e', '#607d8b', '#ff4081',
      '#7c4dff', '#536dfe', '#448aff', '#00bfa5'
    ]

    // Safely extract last two hex chars from address; fallback to stable value
    let tail = '00'
    try {
      if (typeof address === 'string' && address.length > 0) {
        tail = address.replace(/^0x/i, '').slice(-2)
        if (!/^[0-9a-fA-F]{1,2}$/.test(tail)) {
          tail = '00'
        }
      }
    } catch (e) {
      tail = '00'
    }

    const index = parseInt(tail, 16) % colors.length
    return colors[index]
  }

  const getTotalTickets = (): number => {
    // convert to a simple total of bets across participants (betCount)
    const participants = participantsData?.participants || []
    // If backend provides a per-participant betCount, sum it; otherwise approximate by
    // counting participants (1 ticket each) as a conservative fallback.
    return participants.reduce((total: number, p: Participant) => total + ((p as any).betCount ?? 1), 0)
  }

  const safeParticipants = participantsData?.participants || []
  const count = safeParticipants.length

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', p: 1 }}>
      <Box display="flex" alignItems="center" mb={1} justifyContent="center">
        <People sx={{ mr: 1, color: 'white' }} />
        <Typography variant="subtitle1" sx={{ color: 'white' }}>
          ({count})
        </Typography>
      </Box>

      {participantsData?.round_id && (
        <Box mb={1} p={1} sx={{ bgcolor: 'rgba(255, 255, 255, 0.1)', borderRadius: 1 }}>
          <Typography variant="caption" sx={{ color: 'rgba(255, 255, 255, 0.8)' }}>
            Round #{participantsData.round_id} : {participantsData.total_bets} {formatEth((participantsData as any).total_amount_wei ?? 0)} ETH total bets
          </Typography>
        </Box>
      )}

      {loading && count === 0 ? (
        <></>
      ) : count === 0 ? (
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
            Be the first to bet!
          </Typography>
        </Box>
      ) : (
        <Box flex={1} overflow="hidden">
          <List sx={{ overflow: 'auto', maxHeight: '100%', p: 0 }}>
            {safeParticipants.map((participant: Participant, index: number) => (
              <React.Fragment key={participant.address}>
                <ListItem sx={{ px: 1, py: 0.5 }}>
                  <ListItemIcon sx={{ minWidth: 35 }}>
                    <Avatar 
                      sx={{ 
                        bgcolor: getAvatarColor(participant.address ?? '0x0'),
                        width: 28, 
                        height: 28,
                        fontSize: '0.75rem'
                      }}
                    >
                      {(participant.address ?? '0x0').slice(-4).toUpperCase()}
                    </Avatar>
                  </ListItemIcon>
                  <ListItemText
                    primary={
                      <Typography variant="body2" sx={{ color: 'white', fontWeight: 'bold' }}>
                        {formatAddress(participant.address ?? '0x0')}
                      </Typography>
                    }
                    secondary={
                      <Box>
                        <Box display="flex" alignItems="center" gap={0.5} mt={0.5} flexWrap="wrap">
                          <Chip
                            icon={<ConfirmationNumber sx={{ fontSize: '0.7rem !important' }} />}
                            label={formatEth((participant as any).total_bet_amount ?? (participant as any).totalAmountWei ?? 0) + ' ETH'}
                            size="small"
                            sx={{ 
                              height: 18, 
                              fontSize: '0.65rem',
                              bgcolor: 'rgba(76, 175, 80, 0.3)',
                              color: 'white'
                            }}
                          />
                        </Box>
                      </Box>
                    }
                    primaryTypographyProps={{ component: 'div' }}
                    secondaryTypographyProps={{ component: 'div' }}
                  />
                </ListItem>
                {index < safeParticipants.length - 1 && (
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
            Total tickets: {getTotalTickets()}
          </Typography>
        </Box>
      )}
    </Box>
  )
}

export default UserList
