import React, { useState, useEffect } from 'react'
import {
  Typography,
  Box,
  TextField,
  Button,
  Alert,
  CircularProgress,
  Chip,
  Grid,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material'
import { Casino, AccountBalanceWallet, Edit, Person } from '@mui/icons-material'

import { useWalletStore } from '../services/wallet'
import { useLotteryStore } from '../services/lottery'
import { contractService } from '../services/contract'
import api from '../services/api'
import WalletConnection from './WalletConnection'

const BettingPanel: React.FC = () => {
  const { isConnected, address } = useWalletStore()
  const { currentDraw, fetchCurrentDraw } = useLotteryStore()
  const [betAmount, setBetAmount] = useState('')
  const [isPlacingBet, setIsPlacingBet] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [nickname, setNickname] = useState('')
  const [editingNickname, setEditingNickname] = useState(false)
  const [tempNickname, setTempNickname] = useState('')
  const [bettingLimits, setBettingLimits] = useState({ min: '0.001', max: '10', maxBetsPerUser: 10 })
  const [userBetCount, setUserBetCount] = useState(0)

  useEffect(() => {
    if (address) {
      const savedNicknames = localStorage.getItem('userNicknames')
      if (savedNicknames) {
        const nicknames = JSON.parse(savedNicknames)
        setNickname(nicknames[address] || `User ${address.slice(-4)}`)
      } else {
        setNickname(`User ${address.slice(-4)}`)
      }
    }
  }, [address])

  useEffect(() => {
    // Load betting limits from contract
    const loadBettingLimits = async () => {
      try {
        const limits = await contractService.getBettingLimits()
        setBettingLimits(limits)
      } catch (error) {
        console.error('Failed to load betting limits:', error)
      }
    }

    if (isConnected) {
      loadBettingLimits()
    }
  }, [isConnected])

  useEffect(() => {
    // Load user's bet count for current draw
    const loadUserBetCount = async () => {
      if (currentDraw && address) {
        try {
          const userBets = await contractService.getUserBets(currentDraw.draw_id, address)
          setUserBetCount(userBets.length)
        } catch (error) {
          console.error('Failed to load user bet count:', error)
        }
      }
    }

    loadUserBetCount()
  }, [currentDraw, address])

  const handleBetAmountChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value
    if (value === '' || /^\d*\.?\d*$/.test(value)) {
      setBetAmount(value)
      setError('')
    }
  }

  const handleNicknameEdit = () => {
    setTempNickname(nickname)
    setEditingNickname(true)
  }

  const handleNicknameSave = () => {
    if (tempNickname.trim() && address) {
      const savedNicknames = localStorage.getItem('userNicknames')
      const nicknames = savedNicknames ? JSON.parse(savedNicknames) : {}
      nicknames[address] = tempNickname.trim()
      localStorage.setItem('userNicknames', JSON.stringify(nicknames))
      setNickname(tempNickname.trim())
    }
    setEditingNickname(false)
  }

  const validateBetAmount = (): boolean => {
    const amount = parseFloat(betAmount)
    const minBetAmount = parseFloat(bettingLimits.min)
    const maxBetAmount = parseFloat(bettingLimits.max)
    
    if (isNaN(amount) || amount <= 0) {
      setError('Please enter a valid bet amount')
      return false
    }
    
    if (amount < minBetAmount) {
      setError(`Minimum bet is ${bettingLimits.min} ETH`)
      return false
    }
    
    if (amount > maxBetAmount) {
      setError(`Maximum bet is ${bettingLimits.max} ETH`)
      return false
    }
    
    // Check if user has reached betting limit
    if (userBetCount >= bettingLimits.maxBetsPerUser) {
      setError(`You can only place up to ${bettingLimits.maxBetsPerUser} bets per draw`)
      return false
    }
    
    return true
  }

  const handlePlaceBet = async () => {
    if (!isConnected || !address) {
      setError('Please connect your wallet first')
      return
    }

    if (!validateBetAmount()) {
      return
    }

    if (!currentDraw || currentDraw.status !== 'betting') {
      setError('Betting is not available right now')
      return
    }

    setIsPlacingBet(true)
    setError('')
    setSuccess('')

    try {
      // Place bet directly via smart contract
      const transactionHash = await contractService.placeBet(currentDraw.draw_id, betAmount)

      // Optimistically update UI
      setSuccess(`Bet placed successfully! Transaction: ${transactionHash.slice(0, 10)}...`)
      setBetAmount('')
      
      // Reload user bet count
      const userBets = await contractService.getUserBets(currentDraw.draw_id, address)
      setUserBetCount(userBets.length)
      
      // Notify backend for verification (optional)
      try {
        await api.post('/api/verify-bet', {
          user_address: address,
          transaction_hash: transactionHash,
          draw_id: currentDraw.draw_id
        })
      } catch (err) {
        console.warn('Backend verification failed:', err)
      }
      
      // Refresh current draw
      fetchCurrentDraw()
    } catch (err: any) {
      setError(err.message || 'Bet failed')
    } finally {
      setIsPlacingBet(false)
    }
  }

  const calculateTickets = (): number => {
    const amount = parseFloat(betAmount)
    const minBetAmount = parseFloat(bettingLimits.min)
    if (isNaN(amount)) return 0
    return Math.floor(amount / minBetAmount)
  }

  const canPlaceBet = (): boolean => {
    return (
      isConnected &&
      currentDraw?.status === 'betting' &&
      betAmount !== '' &&
      !isPlacingBet
    )
  }

  const formatAddress = (addr: string): string => {
    return `${addr.slice(0, 6)}...${addr.slice(-4)}`
  }

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', p: 1 }}>
  {/* Action buttons */}
      <Box sx={{ mb: 2 }}>
        <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
          <WalletConnection />
          <IconButton 
            size="small" 
            onClick={handleNicknameEdit}
            sx={{ color: 'rgba(255, 255, 255, 0.9)', border: '1px solid rgba(255, 255, 255, 0.3)' }}
            title="Edit nickname"
          >
            <Edit fontSize="small" />
          </IconButton>
          <Button
            variant="contained"
            size="small"
            onClick={handlePlaceBet}
            disabled={!canPlaceBet()}
            startIcon={isPlacingBet ? <CircularProgress size={16} /> : <Casino />}
            sx={{ 
              background: isPlacingBet ? 'rgba(76, 175, 80, 0.3)' : 'linear-gradient(135deg, #4CAF50 0%, #81C784 100%)',
              '&:hover': { background: 'linear-gradient(135deg, #66BB6A 0%, #A5D6A7 100%)' },
              minWidth: '80px'
            }}
          >
            {isPlacingBet ? 'Betting...' : 'Bet'}
          </Button>
          <Button
            variant="outlined"
            size="small"
            onClick={() => setBetAmount(String(parseFloat(betAmount || '0') + 0.01))}
            disabled={!isConnected || currentDraw?.status !== 'betting'}
            sx={{ 
              color: 'white',
              borderColor: 'rgba(255, 255, 255, 0.5)',
              '&:hover': { borderColor: 'white' },
              minWidth: '80px'
            }}
          >
            Add Bet
          </Button>
        </Box>

  {/* Bet amount input */}
        <TextField
          fullWidth
          size="small"
          value={betAmount}
          onChange={handleBetAmountChange}
          disabled={!isConnected || currentDraw?.status !== 'betting' || isPlacingBet}
          placeholder="0.01"
          sx={{
            mb: 1,
            '& .MuiOutlinedInput-root': {
              background: 'rgba(255, 255, 255, 0.1)',
              '& fieldset': { borderColor: 'rgba(255, 255, 255, 0.3)' },
              '&:hover fieldset': { borderColor: 'rgba(255, 255, 255, 0.5)' },
              '&.Mui-focused fieldset': { borderColor: 'rgba(255, 255, 255, 0.7)' },
            },
            '& .MuiInputBase-input': { color: 'white' },
          }}
          InputProps={{
            startAdornment: <AccountBalanceWallet sx={{ mr: 1, color: 'rgba(255, 255, 255, 0.7)' }} />,
            endAdornment: <Typography variant="caption" sx={{ color: 'rgba(255, 255, 255, 0.7)' }}>ETH</Typography>
          }}
        />
        
  {/* Quick bet buttons */}
        <Grid container spacing={1} mb={1}>
          <Grid item xs={4}>
            <Button
              fullWidth
              variant="outlined"
              size="small"
              onClick={() => setBetAmount('0.01')}
              disabled={!isConnected || currentDraw?.status !== 'betting'}
              sx={{ 
                color: 'white',
                borderColor: 'rgba(255, 255, 255, 0.3)',
                '&:hover': { borderColor: 'rgba(255, 255, 255, 0.5)' }
              }}
            >
              0.01
            </Button>
          </Grid>
          <Grid item xs={4}>
            <Button
              fullWidth
              variant="outlined"
              size="small"
              onClick={() => setBetAmount('0.05')}
              disabled={!isConnected || currentDraw?.status !== 'betting'}
              sx={{ 
                color: 'white',
                borderColor: 'rgba(255, 255, 255, 0.3)',
                '&:hover': { borderColor: 'rgba(255, 255, 255, 0.5)' }
              }}
            >
              0.05
            </Button>
          </Grid>
          <Grid item xs={4}>
            <Button
              fullWidth
              variant="outlined"
              size="small"
              onClick={() => setBetAmount('0.1')}
              disabled={!isConnected || currentDraw?.status !== 'betting'}
              sx={{ 
                color: 'white',
                borderColor: 'rgba(255, 255, 255, 0.3)',
                '&:hover': { borderColor: 'rgba(255, 255, 255, 0.5)' }
              }}
            >
              0.1
            </Button>
          </Grid>
        </Grid>

        <Typography variant="caption" sx={{ color: 'rgba(255, 255, 255, 0.6)' }}>
          Range: {bettingLimits.min} - {bettingLimits.max} ETH
        </Typography>
      </Box>

  {/* User info */}
      {isConnected && address && (
        <Box sx={{ 
          mb: 2, 
          p: 1.5, 
          background: 'rgba(255, 255, 255, 0.1)', 
          borderRadius: 1,
          border: '1px solid rgba(255, 255, 255, 0.2)'
        }}>
          <Typography variant="subtitle2" sx={{ color: 'white', mb: 1 }}>
            User Info
          </Typography>
          
          <Box display="flex" alignItems="center" mb={1}>
            <Person sx={{ fontSize: 16, mr: 1, color: 'white' }} />
            <Typography variant="body2" sx={{ color: 'white', fontWeight: 'bold' }}>
              {nickname}
            </Typography>
          </Box>
          
          <Typography variant="caption" sx={{ color: 'rgba(255, 255, 255, 0.8)' }}>
            Wallet: {formatAddress(address)}
          </Typography>
        </Box>
      )}
  {/* Ticket info */}
      {betAmount && calculateTickets() > 0 && (
        <Box mb={2} display="flex" gap={1}>
          <Chip
            size="small"
            label={`${calculateTickets()} ticket(s)`}
            sx={{ 
              bgcolor: 'rgba(76, 175, 80, 0.3)',
              color: 'white',
              border: '1px solid rgba(76, 175, 80, 0.5)'
            }}
          />
          <Chip
            size="small"
            label={`Win chance: ${currentDraw?.participants ? ((calculateTickets() / (currentDraw.participants + calculateTickets())) * 100).toFixed(1) : '100'}%`}
            sx={{ 
              bgcolor: 'rgba(33, 150, 243, 0.3)',
              color: 'white',
              border: '1px solid rgba(33, 150, 243, 0.5)'
            }}
          />
        </Box>
      )}

      {error && (
        <Alert severity="error" sx={{ mb: 1, fontSize: '0.8rem' }}>
          {error}
        </Alert>
      )}

      {success && (
        <Alert severity="success" sx={{ mb: 1, fontSize: '0.8rem' }}>
          {success}
        </Alert>
      )}

      <Typography variant="caption" sx={{ color: 'rgba(255, 255, 255, 0.6)', lineHeight: 1.2 }}>
        • Every {bettingLimits.min} ETH = 1 ticket<br />
        • More tickets, higher winning chance<br />
        • Winner takes the entire pool
      </Typography>

  {/* Nickname edit dialog */}
      <Dialog open={editingNickname} onClose={() => setEditingNickname(false)}>
  <DialogTitle>Edit Nickname</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            fullWidth
            label="Nickname"
            value={tempNickname}
            onChange={(e) => setTempNickname(e.target.value)}
            margin="dense"
            inputProps={{ maxLength: 20 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditingNickname(false)}>Cancel</Button>
          <Button onClick={handleNicknameSave} variant="contained">Save</Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}

export default BettingPanel