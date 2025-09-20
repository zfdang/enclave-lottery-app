import React, { useEffect, useState } from 'react'
import { Typography, Box, List, ListItem, ListItemText, ListItemIcon, Chip, Divider, Avatar } from '@mui/material'
import { History, EmojiEvents, AttachMoney, People } from '@mui/icons-material'

import { getLotteryHistory } from '../services/api'

interface HistoryItem {
  draw_id: string
  draw_time: string
  total_pot: string
  winner: string | null
  winning_number: number | null
  participants: number
}

const HistoryPanel: React.FC = () => {
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [loading, setLoading] = useState(false)

  const fetchHistory = async () => {
    setLoading(true)
    try {
      const response = await getLotteryHistory()
      const list = Array.isArray(response?.history) ? (response.history as HistoryItem[]) : []
      setHistory(list)
    } catch (error) {
      console.error('Error fetching history:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchHistory()
    const interval = setInterval(fetchHistory, 30000)
    return () => clearInterval(interval)
  }, [])

  const formatAddress = (address: string): string => {
    return `${address.slice(0, 6)}...${address.slice(-4)}`
  }

  const formatDate = (timestamp: string): string => {
    const date = new Date(timestamp)
    return `${date.toLocaleDateString()} ${date.toLocaleTimeString().slice(0, 5)}`
  }

  const getAvatarColor = (address: string): string => {
    const colors = [
      '#3f51b5', '#2196f3', '#03a9f4', '#00bcd4',
      '#009688', '#4caf50', '#8bc34a', '#cddc39',
      '#ffeb3b', '#ffc107', '#ff9800', '#ff5722'
    ]
    const index = parseInt(address.slice(-2), 16) % colors.length
    return colors[index]
  }

  const safeHistory = Array.isArray(history) ? history : []

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', p: 1 }}>
      <Box display="flex" alignItems="center" mb={1} justifyContent="center">
        <History sx={{ mr: 1, color: 'white' }} />
        <Typography variant="subtitle1" sx={{ color: 'white' }}>
          History
        </Typography>
      </Box>

      {loading && safeHistory.length === 0 ? (
        <Typography variant="body2" sx={{ color: 'rgba(255, 255, 255, 0.7)', textAlign: 'center' }}>Loading...</Typography>
      ) : safeHistory.length === 0 ? (
        <Box 
          display="flex" 
          flexDirection="column" 
          alignItems="center" 
          justifyContent="center" 
          flex={1}
          sx={{ color: 'rgba(255, 255, 255, 0.7)' }}
        >
          <EmojiEvents sx={{ fontSize: 40, mb: 1 }} />
          <Typography variant="body2" textAlign="center">
            No records yet
          </Typography>
          <Typography variant="caption">
            History will appear here
          </Typography>
        </Box>
      ) : (
        <Box flex={1} overflow="hidden">
          <List sx={{ overflow: 'auto', maxHeight: '100%', p: 0 }}>
            {safeHistory.map((item, index) => (
              <React.Fragment key={item.draw_id}>
                <ListItem sx={{ px: 1, py: 0.5 }}>
                  <ListItemIcon sx={{ minWidth: 35 }}>
                    {item.winner ? (
                      <Avatar 
                        sx={{ 
                          bgcolor: getAvatarColor(item.winner),
                          width: 28, 
                          height: 28,
                        }}
                      >
                        <EmojiEvents sx={{ fontSize: '0.9rem' }} />
                      </Avatar>
                    ) : (
                      <Avatar 
                        sx={{ 
                          bgcolor: 'rgba(255, 255, 255, 0.3)',
                          width: 28, 
                          height: 28,
                          color: 'white'
                        }}
                      >
                        -
                      </Avatar>
                    )}
                  </ListItemIcon>
                  <ListItemText
                    primary={
                      <Box>
                        {item.winner ? (
                          <Typography variant="body2" sx={{ color: 'white', fontWeight: 'bold' }}>
                            Winner: {formatAddress(item.winner)}
                          </Typography>
                        ) : (
                          <Typography variant="body2" sx={{ color: 'rgba(255, 255, 255, 0.8)' }}>
                            No winner
                          </Typography>
                        )}
                      </Box>
                    }
                    secondary={
                      <Box>
                        <Box display="flex" alignItems="center" gap={0.5} mt={0.5} flexWrap="wrap">
                          <Chip
                            icon={<AttachMoney sx={{ fontSize: '0.7rem !important' }} />}
                            label={`${item.total_pot} ETH`}
                            size="small"
                            sx={{ 
                              height: 18, 
                              fontSize: '0.65rem',
                              bgcolor: item.winner ? 'rgba(76, 175, 80, 0.3)' : 'rgba(255, 255, 255, 0.2)',
                              color: 'white'
                            }}
                          />
                          <Chip
                            icon={<People sx={{ fontSize: '0.7rem !important' }} />}
                            label={`${item.participants} users`}
                            size="small"
                            sx={{ 
                              height: 18, 
                              fontSize: '0.65rem',
                              bgcolor: 'rgba(33, 150, 243, 0.3)',
                              color: 'white'
                            }}
                          />
                        </Box>
                        {item.winning_number != null && (
                          <Typography variant="caption" sx={{ color: 'rgba(255, 255, 255, 0.7)' }}>
                            Winning number: #{item.winning_number}
                          </Typography>
                        )}
                        <br />
                        <Typography variant="caption" sx={{ color: 'rgba(255, 255, 255, 0.6)' }}>
                          {formatDate(item.draw_time)}
                        </Typography>
                      </Box>
                    }
                  />
                </ListItem>
                {index < safeHistory.length - 1 && (
                  <Divider sx={{ borderColor: 'rgba(255, 255, 255, 0.2)' }} />
                )}
              </React.Fragment>
            ))}
          </List>
        </Box>
      )}

      {safeHistory.length > 0 && (
        <Box mt={1} pt={1} sx={{ borderTop: '1px solid rgba(255, 255, 255, 0.2)' }}>
          <Typography variant="caption" sx={{ color: 'rgba(255, 255, 255, 0.8)' }} textAlign="center">
            Last {safeHistory.length} draws
          </Typography>
        </Box>
      )}
    </Box>
  )
}

export default HistoryPanel