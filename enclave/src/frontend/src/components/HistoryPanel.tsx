import React, { useEffect, useState } from 'react'
import { Typography, Box, List, ListItem, ListItemText, ListItemIcon, Chip, Divider, Avatar } from '@mui/material'
import { History, EmojiEvents, AttachMoney, People, Undo, EmojiEventsOutlined, MilitaryTech } from '@mui/icons-material'

import { getLotteryHistory } from '../services/api'
import { formatAddress, formatEther, formatTime, generateAvatarColor } from '../utils/helpers'

interface HistoryItem {
  event_type: string  // "RoundCompleted" or "RoundRefunded"
  round_id: number
  participant_count: number
  total_pot_wei: number
  finished_at: number
  winner?: string | null  // Only for RoundCompleted
  winner_prize_wei?: number  // Only for RoundCompleted
  refund_reason?: string | null  // Only for RoundRefunded
}

interface HistoryResponse {
  rounds: HistoryItem[]
  summary: {
    total_rounds: number
    completed_rounds: number
    refunded_rounds: number
    total_volume_wei: number
  }
  pagination: {
    limit: number
    returned: number
  }
  timestamp: string
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
            {historyData.summary.total_rounds} rounds • {((historyData.summary.completed_rounds / Math.max(1, historyData.summary.total_rounds)) * 100).toFixed(1)}% completed
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
                    {item.event_type === 'RoundCompleted' ? (
                      <Avatar 
                        sx={{ 
                          bgcolor: item.winner ? generateAvatarColor(item.winner) : 'rgba(76, 175, 80, 0.5)',
                          width: 28, 
                          height: 28,
                          color: 'white'
                        }}
                      >
                        <EmojiEvents sx={{ fontSize: '0.9rem' }} />
                      </Avatar>
                    ) : item.event_type === 'RoundRefunded' ? (
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
                        {item.winner ? (
                          <Typography variant="body2" sx={{ color: 'white', fontWeight: 'bold' }}>
                            Winner: {formatAddress(item.winner)}
                          </Typography>
                        ) : item.event_type === 'RoundRefunded' ? (
                          <Typography variant="body2" sx={{ color: 'rgba(255, 152, 0, 0.8)' }}>
                            Refunded
                          </Typography>
                        ) : (
                          <Typography variant="body2" sx={{ color: 'rgba(255, 255, 255, 0.8)' }}>
                            {item.event_type}
                          </Typography>
                        )}
                      </Box>
                    }
                    secondary={
                      <Box>
                        <Box display="flex" alignItems="center" gap={0.5} mt={0.5} flexWrap="wrap">
                          <Chip
                            icon={<AttachMoney sx={{ fontSize: '0.7rem !important' }} />}
                            label={`${formatEther(item.total_pot_wei)} ETH`}
                            size="small"
                            sx={{ 
                              height: 18, 
                              fontSize: '0.65rem',
                              bgcolor: item.winner ? 'rgba(76, 175, 80, 0.3)' : item.refund_reason ? 'rgba(255, 152, 0, 0.3)' : 'rgba(255, 255, 255, 0.2)',
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
                        {item.event_type === 'RoundCompleted'  && (
                          <Typography variant="caption" sx={{ color: 'rgba(255, 255, 255, 0.7)' }}>
                            Prize: {formatEther(item.winner_prize_wei ?? 0)} ETH
                          </Typography>
                        )}
                        {item.event_type === 'RoundRefunded' && (
                          <Typography variant="caption" sx={{ color: 'rgba(255, 152, 0, 0.8)' }}>
                            Reason: {item.refund_reason}
                          </Typography>
                        )}
                        <br />
                        <Typography variant="caption" sx={{ color: 'rgba(255, 255, 255, 0.6)' }}>
                          Round #{item.round_id} • {formatTime(item.finished_at)}
                        </Typography>
                      </Box>
                    }
                    primaryTypographyProps={{ component: 'div' }}
                    secondaryTypographyProps={{ component: 'div' }}
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