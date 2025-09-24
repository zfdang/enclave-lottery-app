import React, { useEffect, useState } from 'react'
import {
  Box,
  Container,
  Grid,
  Typography,
  Alert,
  Snackbar,
  AppBar,
  Toolbar,
  Chip,
} from '@mui/material'
import { Security, VerifiedUser, ErrorOutline } from '@mui/icons-material'

import LotteryTimer from './components/LotteryTimer'
import BettingPanel from './components/BettingPanel'
import UserList from './components/UserList'
import HistoryPanel from './components/HistoryPanel'
import ActivityFeed from './components/ActivityFeed'

import { useWebSocket } from './services/websocket'
import { useWalletStore } from './services/wallet'
import { useLotteryStore } from './services/lottery'

function App() {
  const [backendOnline, setBackendOnline] = useState(true)
  const [snackbar, setSnackbar] = useState<{
    open: boolean
    message: string
    severity: 'success' | 'error' | 'warning' | 'info'
  }>({
    open: false,
    message: '',
    severity: 'info'
  })

  const { isConnected } = useWalletStore()
  const { currentDraw, fetchCurrentDraw, error: lotteryError } = useLotteryStore()
  
  // WebSocket connection for real-time updates
  useWebSocket('ws://localhost:6080/ws/lottery', {
    onMessage: (data) => {
      setBackendOnline(true)
      if (data.type === 'bet_placed') {
        setSnackbar({
          open: true,
          message: `New bet placed by ${data.data.user.slice(0, 8)}...`,
          severity: 'info'
        })
        fetchCurrentDraw()
      } else if (data.type === 'draw_completed') {
        setSnackbar({
          open: true,
          message: data.data.winner ? 
            `Draw completed! Winner: ${data.data.winner.slice(0, 8)}...` :
            'Draw completed with no participants',
          severity: 'success'
        })
        fetchCurrentDraw()
      }
    },
    onError: () => {
      setBackendOnline(false)
    },
    onClose: () => {
      setBackendOnline(false)
    }
  })

  useEffect(() => {
    // Check backend status when fetching current draw
    fetchCurrentDraw().then(() => {
      setBackendOnline(true)
    }).catch(() => {
      setBackendOnline(false)
    })
  }, [fetchCurrentDraw])

  // Monitor lottery error state for backend connectivity
  useEffect(() => {
    if (lotteryError) {
      setBackendOnline(false)
    }
  }, [lotteryError])

  const handleCloseSnackbar = () => {
    setSnackbar({ ...snackbar, open: false })
  }

  return (
    <Box sx={{ 
      height: '100vh',
      display: 'flex',
      flexDirection: 'column',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      overflow: 'hidden'
    }}>
  {/* Top area - 10% height */}
      <Box sx={{ height: '10vh', minHeight: '60px' }}>
        <AppBar position="static" sx={{ background: 'rgba(0, 0, 0, 0.2)', height: '100%' }}>
          <Toolbar sx={{ height: '100%' }}>
            <Security sx={{ mr: 2 }} />
            <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
              Lottery Enclave
            </Typography>

            <Chip
              icon={<VerifiedUser />}
              label="Nitro Enclave Verified"
              color="primary"
              variant="outlined"
              sx={{ mr: 2 }}
            />
            
            {/* Backend status indicator */}
            {!backendOnline && (
              <Chip
                icon={<ErrorOutline />}
                label="Backend Offline"
                color="error"
                variant="outlined"
                sx={{ mr: 2, color: '#f44336', borderColor: '#f44336' }}
              />
            )}
            
          </Toolbar>
        </AppBar>
      </Box>

  {/* Main content area - 90% height */}
      <Box sx={{ 
        height: '90vh', 
        display: 'flex',
        padding: 2,
        gap: 2
      }}>
  {/* Left column - Participants (20% width) */}
        <Box sx={{ 
          width: '20%',
          background: 'rgba(255, 255, 255, 0.1)',
          backdropFilter: 'blur(10px)',
          borderRadius: 2,
          border: '1px solid rgba(255, 255, 255, 0.2)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column'
        }}>
          <Typography variant="h6" sx={{ 
            p: 2, 
            borderBottom: '1px solid rgba(255, 255, 255, 0.2)',
            color: 'white',
            textAlign: 'center'
          }}>
            Participants
          </Typography>
          <Box sx={{ flex: 1, overflow: 'auto' }}>
            <UserList />
          </Box>
        </Box>

  {/* Middle column - 60% width */}
        <Box sx={{ 
          width: '60%',
          display: 'flex',
          flexDirection: 'column',
          gap: 2
        }}>
          {/* Live info area - 70% height */}
          <Box sx={{ 
            height: '70%',
            background: 'rgba(255, 255, 255, 0.1)',
            backdropFilter: 'blur(10px)',
            borderRadius: 2,
            border: '1px solid rgba(255, 255, 255, 0.2)',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column'
          }}>
            <Typography variant="h6" sx={{ 
              p: 2, 
              borderBottom: '1px solid rgba(255, 255, 255, 0.2)',
              color: 'white',
              textAlign: 'center'
            }}>
              Live Feed
            </Typography>
            <Box sx={{ flex: 1, overflow: 'auto', p: 1 }}>
              <LotteryTimer />
              <ActivityFeed />
            </Box>
          </Box>

          {/* User actions area - 30% height */}
          <Box sx={{ 
            height: '30%',
            background: 'rgba(255, 255, 255, 0.1)',
            backdropFilter: 'blur(10px)',
            borderRadius: 2,
            border: '1px solid rgba(255, 255, 255, 0.2)',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column'
          }}>

              <BettingPanel />
          </Box>
        </Box>

  {/* Right column - History (20% width) */}
        <Box sx={{ 
          width: '20%',
          background: 'rgba(255, 255, 255, 0.1)',
          backdropFilter: 'blur(10px)',
          borderRadius: 2,
          border: '1px solid rgba(255, 255, 255, 0.2)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column'
        }}>
          <Typography variant="h6" sx={{ 
            p: 2, 
            borderBottom: '1px solid rgba(255, 255, 255, 0.2)',
            color: 'white',
            textAlign: 'center'
          }}>
            History
          </Typography>
          <Box sx={{ flex: 1, overflow: 'auto' }}>
            <HistoryPanel />
          </Box>
        </Box>
      </Box>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert 
          onClose={handleCloseSnackbar} 
          severity={snackbar.severity}
          sx={{ width: '100%' }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  )
}

export default App