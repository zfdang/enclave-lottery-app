import React, { useEffect, useState } from 'react'
import { Typography, Box, List, ListItem, ListItemText, ListItemIcon, Chip, Divider, Avatar } from '@mui/material'
import { History, EmojiEvents, AttachMoney, People, Undo } from '@mui/icons-material'

import { getLotteryHistory } from '../services/api'

interface HistoryItem {
  round_id: number
  final_state: string
  final_state_value: number
  start_time: number
  end_time: number
  total_pot: number
  participant_count: number
  total_bets_placed: number
  winner: string | null
  winner_prize: number
  publisher_commission: number
  sparsity_commission: number
  total_commission: number
  is_completed: boolean
  is_refunded: boolean
  has_winner: boolean
}

interface HistoryResponse {
  rounds: HistoryItem[]
  summary: {
    total_rounds: number
    completed_rounds: number
    refunded_rounds: number
    completion_rate: number
    total_volume: number
    total_prizes_awarded: number
    average_pot_size: number
  }
  pagination: {
    limit: number
    returned_count: number
  }
  timestamp: number
}

const HistoryPanel: React.FC = () => {
  const [historyData, setHistoryData] = useState<HistoryResponse | null>(null)
  const [loading, setLoading] = useState(false)

  const fetchHistory = async () => {
    setLoading(true)
    try {
      const response = await getLotteryHistory(50) // Get last 50 rounds
      setHistoryData(response)
    } catch (error) {
      console.error('Error fetching history:', error)
      setHistoryData(null)
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

  const formatDate = (timestamp: number): string => {
    const date = new Date(timestamp * 1000) // Convert from Unix timestamp
    return `${date.toLocaleDateString()} ${date.toLocaleTimeString().slice(0, 5)}`
  }

  const formatEth = (wei: number): string => {
    return (wei / 1e18).toFixed(4)
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

  const safeHistory = historyData?.rounds || []

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', p: 1 }}>
      <Box display="flex" alignItems="center" mb={1} justifyContent="center">
        <History sx={{ mr: 1, color: 'white' }} />
        <Typography variant="subtitle1" sx={{ color: 'white' }}>
          History
        </Typography>
      </Box>

      {/* Summary Statistics */}
      {historyData?.summary && (
        <Box mb={1} p={1} sx={{ bgcolor: 'rgba(255, 255, 255, 0.1)', borderRadius: 1 }}>
          <Typography variant="caption" sx={{ color: 'rgba(255, 255, 255, 0.8)' }}>
            {historyData.summary.total_rounds} rounds • {(historyData.summary.completion_rate ?? 0).toFixed(1)}% completed
          </Typography>
        </Box>
      )}

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
              <React.Fragment key={item.round_id}>
                <ListItem sx={{ px: 1, py: 0.5 }}>
                  <ListItemIcon sx={{ minWidth: 35 }}>
                    {item.has_winner ? (
                      <Avatar 
                        sx={{ 
                          bgcolor: getAvatarColor(item.winner!),
                          width: 28, 
                          height: 28,
                        }}
                      >
                        <EmojiEvents sx={{ fontSize: '0.9rem' }} />
                      </Avatar>
                    ) : item.is_refunded ? (
                      <Avatar 
                        sx={{ 
                          bgcolor: 'rgba(255, 152, 0, 0.5)',
                          width: 28, 
                          height: 28,
                          color: 'white'
                        }}
                      >
                        <Undo sx={{ fontSize: '0.9rem' }} />
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
                        {item.has_winner ? (
                          <Typography variant="body2" sx={{ color: 'white', fontWeight: 'bold' }}>
                            Winner: {formatAddress(item.winner!)}
                          </Typography>
                        ) : item.is_refunded ? (
                          <Typography variant="body2" sx={{ color: 'rgba(255, 152, 0, 0.8)' }}>
                            Refunded
                          </Typography>
                        ) : (
                          <Typography variant="body2" sx={{ color: 'rgba(255, 255, 255, 0.8)' }}>
                            {item.final_state}
                          </Typography>
                        )}
                      </Box>
                    }
                    secondary={
                      <Box>
                        <Box display="flex" alignItems="center" gap={0.5} mt={0.5} flexWrap="wrap">
                          <Chip
                            icon={<AttachMoney sx={{ fontSize: '0.7rem !important' }} />}
                            label={`${formatEth(item.total_pot)} ETH`}
                            size="small"
                            sx={{ 
                              height: 18, 
                              fontSize: '0.65rem',
                              bgcolor: item.has_winner ? 'rgba(76, 175, 80, 0.3)' : item.is_refunded ? 'rgba(255, 152, 0, 0.3)' : 'rgba(255, 255, 255, 0.2)',
                              color: 'white'
                            }}
                          />
                          <Chip
                            icon={<People sx={{ fontSize: '0.7rem !important' }} />}
                            label={`${item.participant_count} users`}
                            size="small"
                            sx={{ 
                              height: 18, 
                              fontSize: '0.65rem',
                              bgcolor: 'rgba(33, 150, 243, 0.3)',
                              color: 'white'
                            }}
                          />
                        </Box>
                        {item.has_winner && (
                          <Typography variant="caption" sx={{ color: 'rgba(255, 255, 255, 0.7)' }}>
                            Prize: {formatEth(item.winner_prize)} ETH
                          </Typography>
                        )}
                        <br />
                        <Typography variant="caption" sx={{ color: 'rgba(255, 255, 255, 0.6)' }}>
                          Round #{item.round_id} • {formatDate(item.end_time)}
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
            Last {safeHistory.length} rounds
          </Typography>
        </Box>
      )}
    </Box>
  )
}

export default HistoryPanel