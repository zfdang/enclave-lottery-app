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
import { getLotteryContract } from './services/api'

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

  // Contract info state (moved from ActivityFeed)
  const [contractAddress, setContractAddress] = useState<string | null>(null)
  const [rpcUrl, setRpcUrl] = useState<string | null>(null)
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
    drawDelay: string
    minPart: string
    sparsityIsSet: boolean
  }>(null)

  const formatAddress = (address: string): string => `${address.slice(0, 6)}...${address.slice(-4)}`

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

  // Fetch contract address from backend
  const fetchContractAddress = async () => {
    setContractLoading(true)
    setContractError(null)
    try {
      const data = await getLotteryContract()
      setContractAddress(data.contract_address || null)
      setRpcUrl(data.network || null)
    } catch (e: any) {
      setContractError(e.message || 'Unable to load contract info')
      setContractAddress(null)
    } finally {
      setContractLoading(false)
    }
  }

  useEffect(() => {
    fetchContractAddress()
  }, [])

  // Fetch contract config directly from chain using read-only provider
  const fetchContractConfig = async () => {
    if (!contractAddress) return
    setConfigLoading(true)
    setConfigError(null)
    setContractConfig(null)
    try {
      // Try to load ABI from static mount; on dev fallback to public path
      let abiRes = await fetch('/static/contracts/compiled/Lottery.abi')
      if (!abiRes.ok) {
        abiRes = await fetch('/contracts/compiled/Lottery.abi')
      }
      if (!abiRes.ok) throw new Error('Failed to fetch ABI')
      const abiText = await abiRes.text()
      const abi = JSON.parse(abiText)

      const url = rpcUrl && rpcUrl !== 'unknown' ? rpcUrl : 'http://localhost:8545'
      const provider = new ethers.JsonRpcProvider(url)
      const contract = new ethers.Contract(contractAddress, abi, provider)
      const cfg = await contract.getConfig()

      const normalized = {
        publisherAddr: cfg.publisherAddr,
        sparsityAddr: cfg.sparsityAddr,
        operatorAddr: cfg.operatorAddr,
        publisherCommission: cfg.publisherCommission?.toString?.() ?? String(cfg[3]),
        sparsityCommission: cfg.sparsityCommission?.toString?.() ?? String(cfg[4]),
        minBet: cfg.minBet?.toString?.() ?? String(cfg[5]),
        bettingDur: cfg.bettingDur?.toString?.() ?? String(cfg[6]),
        drawDelay: cfg.drawDelay?.toString?.() ?? String(cfg[7]),
        minPart: cfg.minPart?.toString?.() ?? String(cfg[8]),
        sparsityIsSet: Boolean(cfg.sparsityIsSet ?? cfg[9])
      }
      setContractConfig(normalized)
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
              sx={{
                mr: 2,
                fontWeight: 700,
                fontSize: '1rem',
                px: 2,
                py: 1,
                borderWidth: 2,
                borderStyle: 'solid',
                borderColor: backendOnline ? '#4caf50' : '#f44336',
                background: backendOnline ? 'rgba(76, 175, 80, 0.15)' : 'rgba(244, 67, 54, 0.15)',
                color: backendOnline ? '#388e3c' : '#b71c1c',
                boxShadow: backendOnline
                  ? '0 0 8px 2px rgba(76,175,80,0.3)'
                  : '0 0 8px 2px rgba(244,67,54,0.3)',
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
                Live Feed
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
                      fontWeight: 700,
                      fontSize: '1rem',
                      px: 2,
                      py: 1,
                      borderWidth: 2,
                      borderStyle: 'solid',
                      borderColor: '#1976d2',
                      background: 'rgba(33,150,243,0.15)',
                      color: '#0d47a1',
                      boxShadow: '0 0 8px 2px rgba(33,150,243,0.25)',
                      cursor: 'pointer',
                      transition: 'all 0.2s',
                    }}
                    onClick={() => { setConfigOpen(true); fetchContractConfig(); }}
                  />
                ) : null}
              </Box>
            </Box>
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

      {/* Contract Configuration Dialog */}
      <Dialog open={configOpen} onClose={() => setConfigOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>
          <Box display="flex" alignItems="center">
            <VerifiedUser sx={{ mr: 1 }} />
            Lottery Contract Configuration
          </Box>
        </DialogTitle>
        <DialogContent>
          {configLoading ? (
            <Typography>Loading contract configuration...</Typography>
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
                The following configuration is fetched directly from the contract on-chain. You can verify these values independently.
              </Typography>
              <Box sx={{ display: 'grid', gridTemplateColumns: '1fr', gap: 1 }}>
                <Typography variant="body2"><strong>Publisher:</strong> {contractConfig.publisherAddr}</Typography>
                <Typography variant="body2"><strong>Sparsity:</strong> {contractConfig.sparsityAddr}</Typography>
                <Typography variant="body2"><strong>Operator:</strong> {contractConfig.operatorAddr}</Typography>
                <Typography variant="body2"><strong>Publisher Commission:</strong> {contractConfig.publisherCommission}</Typography>
                <Typography variant="body2"><strong>Sparsity Commission:</strong> {contractConfig.sparsityCommission}</Typography>
                <Typography variant="body2"><strong>Min Bet (wei):</strong> {contractConfig.minBet}</Typography>
                <Typography variant="body2"><strong>Betting Duration (s):</strong> {contractConfig.bettingDur}</Typography>
                <Typography variant="body2"><strong>Draw Delay (s):</strong> {contractConfig.drawDelay}</Typography>
                <Typography variant="body2"><strong>Min Participants:</strong> {contractConfig.minPart}</Typography>
                <Typography variant="body2"><strong>Sparsity Set:</strong> {contractConfig.sparsityIsSet ? 'Yes' : 'No'}</Typography>
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