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
  bets: Array<{
    amount: number
    ticket_numbers: number[]
    timestamp: string
  }>
  total_bet_amount: number
  bet_count: number
  ticket_numbers: number[]
}

interface ParticipantsResponse {
  round_id: number | null
  round_state?: string
  participants: Participant[]
  total_participants: number
  total_bets: number
  total_bet_amount: number
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
    const colors = [
      '#f44336', '#e91e63', '#9c27b0', '#673ab7',
      '#3f51b5', '#2196f3', '#03a9f4', '#00bcd4',
      '#009688', '#4caf50', '#8bc34a', '#cddc39'
    ]
    const index = parseInt(address.slice(-2), 16) % colors.length
    return colors[index]
  }

  const getTotalTickets = (): number => {
    const participants = participantsData?.participants || []
    return participants.reduce((total: number, participant: Participant) => {
      // participant.ticket_numbers may be undefined if backend uses a different shape.
      if (Array.isArray((participant as any).ticket_numbers)) {
        return total + (participant as any).ticket_numbers.length
      }
      // Fallback to bets array length or bet_count if present
      if (Array.isArray((participant as any).bets)) {
        return total + (participant as any).bets.length
      }
      return total + ((participant as any).bet_count ?? 0)
    }, 0)
  }

  const getWinChance = (ticketCount: number): string => {
    const total = getTotalTickets()
    if (total === 0) return '0%'
    return ((ticketCount / total) * 100).toFixed(1) + '%'
  }

  const safeParticipants = participantsData?.participants || []
  const count = safeParticipants.length

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', p: 1 }}>
      <Box display="flex" alignItems="center" mb={1} justifyContent="center">
        <People sx={{ mr: 1, color: 'white' }} />
        <Typography variant="subtitle1" sx={{ color: 'white' }}>
          Participants ({count})
        </Typography>
      </Box>

      {participantsData?.round_id && (
        <Box mb={1} p={1} sx={{ bgcolor: 'rgba(255, 255, 255, 0.1)', borderRadius: 1 }}>
          <Typography variant="caption" sx={{ color: 'rgba(255, 255, 255, 0.8)' }}>
            Round #{participantsData.round_id} • {participantsData.total_bets} bets • {formatEth(participantsData.total_bet_amount)} ETH total
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
                          <Chip
                            icon={<ConfirmationNumber sx={{ fontSize: '0.7rem !important' }} />}
                            label={(Array.isArray((participant as any).ticket_numbers) ? (participant as any).ticket_numbers.length : Array.isArray((participant as any).bets) ? (participant as any).bets.length : ((participant as any).bet_count ?? 0)) + ' tickets'}
                            size="small"
                            sx={{ 
                              height: 18, 
                              fontSize: '0.65rem',
                              bgcolor: 'rgba(33, 150, 243, 0.3)',
                              color: 'white'
                            }}
                          />
                        </Box>
                        <Typography variant="caption" sx={{ color: 'rgba(255, 255, 255, 0.7)' }}>
                          Win chance: {getWinChance(Array.isArray((participant as any).ticket_numbers) ? (participant as any).ticket_numbers.length : Array.isArray((participant as any).bets) ? (participant as any).bets.length : ((participant as any).bet_count ?? 0))}
                        </Typography>
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
