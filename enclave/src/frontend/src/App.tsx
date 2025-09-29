import React, { useEffect, useState, useCallback } from 'react'
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
  Button,
  CircularProgress
} from '@mui/material'
import { Security, VerifiedUser, ErrorOutline } from '@mui/icons-material'
import { ethers } from 'ethers'

import LotteryTimer from './components/LotteryTimer'
import BettingPanel from './components/BettingPanel'
import UserList from './components/UserList'
import HistoryPanel from './components/HistoryPanel'
import ActivityFeed from './components/ActivityFeed'

import { useWebSocket } from './services/websocket'
import { useWalletStore } from './services/wallet'
import { useLotteryStore } from './services/lottery'
import { getContractAddress, getHealth } from './services/api'
import { contractService } from './services/contract'
import { log } from 'console'

function App() {
  const [backendOnline, setBackendOnline] = useState(false)
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
  const { roundStatus, fetchRoundStatus, error: lotteryError } = useLotteryStore()
  
  // Health check function
  const checkBackendHealth = useCallback(async () => {
    try {
      const health = await getHealth()
      const isHealthy = health?.status === 'ok'
      setBackendOnline(isHealthy)
      return isHealthy
    } catch (error) {
      setBackendOnline(false)
      return false
    }
  }, [])

  // Periodic health check
  useEffect(() => {
    // Initial health check
    checkBackendHealth()
    
    // Set up periodic health checks every 10 seconds
    const healthCheckInterval = setInterval(checkBackendHealth, 10000)
    
    return () => {
      clearInterval(healthCheckInterval)
    }
  }, [checkBackendHealth])
  
  // WebSocket connection for real-time updates
  const rawWs = import.meta.env.VITE_WEBSOCKET_URL
  let wsUrl = rawWs || "ws://127.0.0.1/ws/lottery"

  useWebSocket(wsUrl, {
    onMessage: (data) => {
      if (data.type === 'bet_placed') {
        setSnackbar({
          open: true,
          message: `New bet placed by ${data.data.user.slice(0, 8)}...`,
          severity: 'info'
        })
        fetchRoundStatus()
      } else if (data.type === 'draw_completed') {
        setSnackbar({
          open: true,
          message: data.data.winner ? 
            `Draw completed! Winner: ${data.data.winner.slice(0, 8)}...` :
            'Draw completed with no participants',
          severity: 'success'
        })
        fetchRoundStatus()
      }
    },
    // Remove onError and onClose handlers since we use health checks only
    onError: () => {},
    onClose: () => {}
  })

  useEffect(() => {
    // Fetch current draw on component mount
    fetchRoundStatus()
  }, [fetchRoundStatus])

  const handleCloseSnackbar = () => {
    setSnackbar({ ...snackbar, open: false })
  }

  const [attestationOpen, setAttestationOpen] = useState(false);
  const [attestation, setAttestation] = useState<string>('');
  const [attestationLoading, setAttestationLoading] = useState(false);
  const [attestationError, setAttestationError] = useState('');

  // Contract info state (moved from ActivityFeed)
  const [contractAddress, setContractAddress] = useState<string | null>(null)
  const rpcUrl = import.meta.env.VITE_RPC_URL
  const chainId = import.meta.env.VITE_CHAIN_ID
  const [contractLoading, setContractLoading] = useState<boolean>(false)
  const [contractError, setContractError] = useState<string | null>(null)

  // Contract config dialog state
  const [configOpen, setConfigOpen] = useState(false)
  const [configLoading, setConfigLoading] = useState(false)
  const [configError, setConfigError] = useState<string | null>(null)
  const [contractConfig, setContractConfig] = useState<null | {
    publisherAddr: string
    sparsityAddr: string
    operatorAddr: string
    publisherCommission: string
    sparsityCommission: string
    minBet: string
    bettingDur: string
    minDrawDelay: string
    maxDrawDelay: string
    minEndTimeExt: string
    minPart: string
  }>(null)
  // Round information fetched from chain
  const [roundInfo, setRoundInfo] = useState<null | {
    roundId: number
    startTime: number
    endTime: number
    minDrawTime: number
    maxDrawTime: number
    totalPotEth: string
    participantCount: number
    state: number
  }>(null)

  const formatAddress = (address: string): string => `${address.slice(0, 6)}...${address.slice(-4)}`

  const formatTime = (t?: number | null) => {
    if (!t || Number(t) <= 0) return 'N/A'
    try {
      return new Date(Number(t) * 1000).toLocaleString()
    } catch (e) {
      return 'N/A'
    }
  }

  const roundStateLabel = (state: number) => {
    switch (state) {
      case 0:
        return 'WAITING'
      case 1:
        return 'BETTING'
      case 2:
        return 'DRAWING'
      case 3:
        return 'COMPLETED'
      case 4:
        return 'REFUNDED'
      default:
        return `UNKNOWN(${state})`
    }
  }

  const handleAttestationClick = async () => {
    setAttestationOpen(true);
    setAttestationLoading(true);
    setAttestationError('');
    try {
      // Fetch attestation from backend via centralized API helper
      const data = await (await import('./services/api')).getAttestation();
      setAttestation(JSON.stringify(data, null, 2));
    } catch (err: any) {
      setAttestationError(err?.message || 'Error fetching attestation');
    } finally {
      setAttestationLoading(false);
    }
  };

  const handleAttestationClose = () => {
    setAttestationOpen(false);
    setAttestation('');
    setAttestationError('');
  };

  // Fetch contract address from backend (simplified) and retry every 30 seconds until found
  useEffect(() => {
    let mounted = true
    let isFetching = false
    let intervalId: ReturnType<typeof setInterval> | null = null

    const attemptFetch = async () => {
      if (!mounted || isFetching) return
      isFetching = true
      setContractLoading(true)
      setContractError(null)
      try {
        const data = await getContractAddress()
        if (!mounted) return
        const addr = data?.contract_address ?? null
        if (addr) {
          setContractAddress(addr)
          contractService.setContractAddress(addr)
          console.log('App: Loaded contract address from API:', addr)

          // Found valid address: stop retries
          if (intervalId) {
            clearInterval(intervalId)
            intervalId = null
          }
        } else {
          // No address yet; keep trying
          setContractAddress(null)
          setContractError(null)
          console.log('App: No contract address yet; will retry')
        }
      } catch (e: any) {
        if (!mounted) return
        setContractError(e.message || 'Unable to load contract info')
        setContractAddress(null)
        console.warn('App: Error fetching contract address, will retry:', e)
      } finally {
        if (!mounted) return
        setContractLoading(false)
        isFetching = false
      }
    }

    // Initial attempt immediately
    attemptFetch()

    // Retry every 30 seconds until we have a valid address
    intervalId = setInterval(() => {
      attemptFetch()
    }, 30000)

    return () => {
      mounted = false
      if (intervalId) clearInterval(intervalId)
    }
  }, [])

  // Fetch contract config using centralized contract service
  const fetchContractDetails = async () => {
    if (!contractAddress) return
    setConfigLoading(true)
    setConfigError(null)
    setContractConfig(null)
    setRoundInfo(null)
    
    try {
      const url = rpcUrl
      console.log("RPC URL:", url)
      
      // Fetch contract configuration first (RPC-based helper)
      const normalized = await contractService.getContractConfig()

      // Update UI with contract config immediately
      setContractConfig(normalized)

      // Now attempt to fetch round info via contractService (RPC-based helper)
      try {
        const round = await contractService.getRound()

        console.log('getRound result:', round)

        const normalizedRound = round ? {
          roundId: Number(round.roundId),
          startTime: Number(round.startTime),
          endTime: Number(round.endTime),
          minDrawTime: Number(round.minDrawTime),
          maxDrawTime: Number(round.maxDrawTime),
          totalPotEth: String(round.totalPot),
          participantCount: Number(round.participantCount),
          state: Number(round.state)
        } : null

        setRoundInfo(normalizedRound)
      } catch (err) {
        // leave roundInfo null but keep config
        console.warn('Failed to fetch round info:', err)
        setRoundInfo(null)
      }
    } catch (e: any) {
      setConfigError(e.message || 'Failed to load contract config')
    } finally {
      setConfigLoading(false)
    }
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
      <Box sx={{ height: '8vh', minHeight: '54px' }}>
        <AppBar position="static" sx={{ background: 'rgba(0, 0, 0, 0.2)', height: '100%' }}>
          <Toolbar sx={{ height: '100%', alignItems: 'center', minHeight: '48px' }}>
            <Security sx={{ mr: 2 }} />
            <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
              Lottery (Powered by Sparsity)
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
              sx={{
                mr: 2,
                fontWeight: 600,
                fontSize: '1rem',
                px: 2,
                py: 0.5,
                borderWidth: 1.5,
                borderStyle: 'solid',
                borderColor: backendOnline ? 'rgba(65, 226, 94, 0.7)' : 'rgba(244,67,54,0.5)',
                background: backendOnline ? 'linear-gradient(90deg, rgba(102,126,234,0.10) 0%, rgba(118,75,162,0.10) 100%)' : 'rgba(244,67,54,0.08)',
                color: backendOnline ? '#b4bdeaff' : '#b71c1c',
                borderRadius: 2,
                boxShadow: '0 1px 6px 0 rgba(102,126,234,0.08)',
                cursor: backendOnline ? 'pointer' : 'not-allowed',
                opacity: backendOnline ? 1 : 0.7,
                transition: 'all 0.2s',
              }}
              clickable={backendOnline}
              onClick={backendOnline ? handleAttestationClick : undefined}
            />
            
          </Toolbar>
        </AppBar>
      </Box>

  {/* Main content area - 90% height */}
      <Box sx={{ 
        height: '92vh', 
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
          {/* Live info area - 75% height */}
          <Box sx={{ 
            height: '75%',
            background: 'rgba(255, 255, 255, 0.1)',
            backdropFilter: 'blur(10px)',
            borderRadius: 2,
            border: '1px solid rgba(255, 255, 255, 0.2)',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column'
          }}>
            <Box sx={{
              position: 'relative',
              p: 2,
              borderBottom: '1px solid rgba(255, 255, 255, 0.2)',
              color: 'white',
              width: '100%',
              minHeight: 56,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              <Box sx={{
                fontWeight: 600,
                fontSize: '1.00rem',
                margin: '0 auto',
                textAlign: 'center',
                width: 'fit-content',
              }}>
                Lottery Status
              </Box>
              <Box sx={{
                position: 'absolute',
                right: 16,
                top: '50%',
                transform: 'translateY(-50%)',
                display: 'flex',
                alignItems: 'center',
              }}>
                {contractLoading ? (
                  <Chip
                    label={
                      <Box display="inline-flex" alignItems="center" gap={1}>
                        <CircularProgress size={12} />
                        Loading contract...
                      </Box>
                    }
                    size="small"
                    sx={{ bgcolor: 'rgba(255,255,255,0.15)', color: 'white' }}
                  />
                ) : contractError ? (
                  <Chip
                    label="No active contract"
                    color="default"
                    size="small"
                    sx={{ bgcolor: 'rgba(255,255,255,0.15)', color: 'white' }}
                  />
                ) : contractAddress ? (
                  <Chip
                    label={`Contract ${formatAddress(contractAddress)}`}
                    color="primary"
                    variant="outlined"
                    sx={{
                      fontWeight: 600,
                      fontSize: '1rem',
                      px: 2,
                      py: 1,
                      borderWidth: 1.5,
                      borderStyle: 'solid',
                      borderColor: 'rgba(65, 226, 94, 0.7)',
                      background: 'linear-gradient(90deg, rgba(102,126,234,0.10) 0%, rgba(118,75,162,0.10) 100%)',
                      color: '#b4bdeaff',
                      borderRadius: 2,
                      boxShadow: '0 1px 6px 0 rgba(102,126,234,0.08)',
                      cursor: 'pointer',
                      transition: 'all 0.2s',
                    }}
                    onClick={() => { setConfigOpen(true); fetchContractDetails(); }}
                  />
                ) : null}
              </Box>
            </Box>
            <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', p: 1 }}>
              {/* Keep LotteryTimer fixed at top of this area */}
              <Box sx={{ flex: '0 0 auto' }}>
                <LotteryTimer />
              </Box>

              {/* ActivityFeed should scroll independently */}
              <Box sx={{
                flex: '1 1 auto',
                overflowY: 'scroll',
                overflowX: 'hidden',
                mt: 1,
                /* Always show a vertical scrollbar for affordance */
                '&::-webkit-scrollbar': { width: '10px' },
                '&::-webkit-scrollbar-thumb': { backgroundColor: 'rgba(255,255,255,0.08)', borderRadius: 8 },
              }}>
                <ActivityFeed />
              </Box>
            </Box>
          </Box>

          {/* User actions area - 25% height */}
          <Box sx={{ 
            height: '25%',
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

      {/* Contract Configuration Dialog */}
      <Dialog open={configOpen} onClose={() => setConfigOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>
          <Box display="flex" alignItems="center">
            <VerifiedUser sx={{ mr: 1 }} />
            Lottery Contract Information
          </Box>
        </DialogTitle>
        <DialogContent>
          {configLoading ? (
            <Typography>Loading contract information from blockchain...</Typography>
          ) : configError ? (
            <Alert severity="error">{configError}</Alert>
          ) : contractConfig ? (
            <>
              <Alert severity="info" sx={{ mb: 2 }}>
                This contract is deployed and managed by the enclave backend. The address below is the live contract currently in use.
              </Alert>
              <Box sx={{ backgroundColor: 'rgba(0, 0, 0, 0.07)', p: 2, borderRadius: 1, mb: 2 }}>
                <Typography variant="caption" color="text.secondary">
                  Contract Address
                </Typography>
                <Typography variant="body2" fontFamily="monospace" sx={{
                  wordBreak: 'break-all',
                  whiteSpace: 'pre-wrap',
                  fontSize: '0.95rem',
                  color: '#1976d2',
                  fontWeight: 700,
                  mb: 1
                }}>
                  {contractAddress}
                </Typography>
              </Box>
              <Typography variant="body2" color="text.secondary" paragraph>
                The following infromation is fetched directly from the contract on-chain. You can verify these values independently.
              </Typography>
              <Box sx={{ display: 'grid', gridTemplateColumns: '1fr', gap: 1 }}>
                {roundInfo ? (
                  <>
                    <Typography variant="h6" sx={{ mt: 2 }}>Current Round</Typography>
                    <Typography variant="body2"><strong>Round ID:</strong> {roundInfo.roundId}</Typography>
                    <Typography variant="body2"><strong>Betting Time:</strong> {formatTime(roundInfo.startTime)} ~ {formatTime(roundInfo.endTime)}</Typography>
                    <Typography variant="body2"><strong>Draw Time:</strong> {formatTime(roundInfo.minDrawTime)} ~ {formatTime(roundInfo.maxDrawTime)}</Typography>
                    <Typography variant="body2"><strong>Total Pot (ETH):</strong> {roundInfo.totalPotEth}</Typography>
                    <Typography variant="body2"><strong>Participants:</strong> {roundInfo.participantCount}</Typography>
                    <Typography variant="body2"><strong>State:</strong> {roundStateLabel(roundInfo.state)}</Typography>
                  </>
                ) : null}
                <>
                  <Typography variant="h6" sx={{ mt: 2 }}>Overall Config</Typography>
                  <Typography variant="body2"><strong>Publisher:</strong> {contractConfig.publisherAddr}</Typography>
                  <Typography variant="body2"><strong>Sparsity:</strong> {contractConfig.sparsityAddr}</Typography>
                  <Typography variant="body2"><strong>Operator:</strong> {contractConfig.operatorAddr}</Typography>
                  <Typography variant="body2"><strong>Publisher Commission:</strong> {contractConfig.publisherCommission}</Typography>
                  <Typography variant="body2"><strong>Sparsity Commission:</strong> {contractConfig.sparsityCommission}</Typography>
                  <Typography variant="body2"><strong>Min Bet (wei):</strong> {contractConfig.minBet}</Typography>
                  <Typography variant="body2"><strong>Betting Duration (s):</strong> {contractConfig.bettingDur}</Typography>
                  <Typography variant="body2"><strong>Min Draw Delay (s):</strong> {contractConfig.minDrawDelay}</Typography>
                  <Typography variant="body2"><strong>Max Draw Delay (s):</strong> {contractConfig.maxDrawDelay}</Typography>
                  <Typography variant="body2"><strong>Min Participants:</strong> {contractConfig.minPart}</Typography>
                </>
              </Box>
            </>
          ) : (
            <Typography variant="body2">No configuration available.</Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfigOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}

export default App