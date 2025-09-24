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
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button
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

  const [attestationOpen, setAttestationOpen] = useState(false);
  const [attestation, setAttestation] = useState<string>('');
  const [attestationLoading, setAttestationLoading] = useState(false);
  const [attestationError, setAttestationError] = useState('');

  const handleAttestationClick = async () => {
    setAttestationOpen(true);
    setAttestationLoading(true);
    setAttestationError('');
    try {
      // Fetch attestation from backend
      const response = await fetch('/api/attestation');
      if (!response.ok) throw new Error('Failed to fetch attestation');
      const data = await response.json();
      setAttestation(JSON.stringify(data, null, 2));
    } catch (err: any) {
      setAttestationError(err.message || 'Error fetching attestation');
    } finally {
      setAttestationLoading(false);
    }
  };

  const handleAttestationClose = () => {
    setAttestationOpen(false);
    setAttestation('');
    setAttestationError('');
  };

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
            
            <Chip
              icon={<VerifiedUser />}
              label="Nitro Enclave Verified"
              color="primary"
              variant="outlined"
              sx={{ mr: 2, cursor: backendOnline ? 'pointer' : 'not-allowed', opacity: backendOnline ? 1 : 0.5 }}
              clickable={backendOnline}
              onClick={backendOnline ? handleAttestationClick : undefined}
            />
            
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

      {/* Enclave Attestation Dialog */}
      <Dialog 
        open={attestationOpen} 
        onClose={handleAttestationClose}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          <Box display="flex" alignItems="center">
            <VerifiedUser sx={{ mr: 1 }} />
            Enclave Attestation
          </Box>
        </DialogTitle>
        <DialogContent>
          {attestationLoading ? (
            <Typography>Loading attestation...</Typography>
          ) : attestationError ? (
            <Alert severity="error">{attestationError}</Alert>
          ) : (
            <>
              <Alert severity="success" sx={{ mb: 2 }}>
                This lottery application is running in a verified AWS Nitro Enclave
              </Alert>
              
              <Typography variant="body2" color="text.secondary" paragraph>
                The enclave attestation document proves that this application is running in a secure, 
                isolated environment where no one (including AWS or the host) can access the lottery logic.
              </Typography>
              
              <Box sx={{ backgroundColor: 'rgba(0, 0, 0, 0.1)', p: 2, borderRadius: 1, mb: 2 }}>
                <Typography variant="caption" color="text.secondary">
                  Attestation Document
                </Typography>
                <Typography variant="body2" fontFamily="monospace" sx={{ 
                  wordBreak: 'break-all',
                  whiteSpace: 'pre-wrap',
                  fontSize: '0.75rem',
                  maxHeight: '300px',
                  overflow: 'auto'
                }}>
                  {attestation}
                </Typography>
              </Box>
              
              <Typography variant="body2" color="text.secondary">
                You can independently verify this attestation document to ensure the integrity 
                of the lottery system and that no tampering is possible.
              </Typography>
            </>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={handleAttestationClose}>
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}

export default App