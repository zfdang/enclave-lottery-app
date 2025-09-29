import React, { useState, useEffect } from 'react'
import {
  Typography,
  Box,
  Button,
  Alert,
  CircularProgress,
  IconButton,
  Dialog,
} from '@mui/material'
import { Casino, Add, Remove } from '@mui/icons-material'

import { useWalletStore } from '../services/wallet'
import { useLotteryStore } from '../services/lottery'
import { contractService } from '../services/contract'
import api, { getPlayerInfo } from '../services/api'
import { isAddress } from 'ethers'
import WalletConnection from './WalletConnection'

const BettingPanel: React.FC = () => {
  const [dialogOpen, setDialogOpen] = useState(false)
  const [unmetConditions, setUnmetConditions] = useState<string[]>([])
  const { isConnected, address } = useWalletStore()
  const { roundStatus, fetchRoundStatus } = useLotteryStore()
  const [isPlacingBet, setIsPlacingBet] = useState(false)
  const [notificationOpen, setNotificationOpen] = useState(false)
  const [notificationMessage, setNotificationMessage] = useState('')
  const [notificationSeverity, setNotificationSeverity] = useState<'success' | 'error' | 'info' | 'warning'>('info')
  const [userBetAmount, setUserBetAmount] = useState(0)
  const [userWinRate, setUserWinRate] = useState<number | null>(null)
  // default value for BASE_BET
  const BASE_BET = '0.01' // Fixed base bet amount in ETH
  const [minBetAmount, setMinBetAmount] = useState<string | null>(null)
  const [ones, setOnes] = useState(1)
  const [tens, setTens] = useState(0)
  const [hundreds, setHundreds] = useState(0)

  
  useEffect(() => {
    // Load user's bet amount for current draw
    const loadUserBetAmount = async () => {
      if (roundStatus && address) {
        try {
          // Use backend API to get player's total bet in the current round (wei) and win rate
          const resp = await getPlayerInfo(address)
          const wei = Number(resp?.totalAmountWei ?? 0)
          const eth = wei / 1e18
          setUserBetAmount(eth)
          // winRate returned as percentage (0-100)
          setUserWinRate(typeof resp?.winRate === 'number' ? resp.winRate : null)
        } catch (error) {
          console.error('Failed to load user bet info:', error)
          setUserWinRate(null)
        }
      }
    }

    loadUserBetAmount()
  }, [roundStatus, address])

  // Load min bet amount from contract (RPC getter)
  useEffect(() => {
    const loadMinBet = async () => {
      try {
        if (!contractService.hasValidContractAddress()) return
        const mb = await contractService.getMinBetAmount()
        setMinBetAmount(mb)
      } catch (err) {
        console.warn('Failed to load min bet amount:', err)
      }
    }

    loadMinBet()
  }, [isConnected, roundStatus])

  const getTotalMultiplier = (): number => {
    return ones + tens * 10 + hundreds * 100
  }

  const getTotalBetAmount = (): number => {
    const base = minBetAmount ?? BASE_BET
    return parseFloat(base) * getTotalMultiplier()
  }

  const calculateWinRate = (): number => {
    // Prefer server-provided estimate when available
    if (typeof userWinRate === 'number') return userWinRate
    if (!roundStatus || !isConnected || userBetAmount === 0) return 0
    const totalPot = parseFloat(roundStatus.total_pot?.toString() || '0')
    const base = minBetAmount ?? BASE_BET
    const userTickets = userBetAmount / parseFloat(base)
    const totalTickets = totalPot / parseFloat(base)
    return totalTickets > 0 ? (userTickets / totalTickets) * 100 : 0
  }

  const handlePlaceBet = async () => {
    // Collect unmet conditions
    const unmet: string[] = []
    if (!isConnected || !address) {
      unmet.push('Wallet is not connected.')
    }
    // if (!roundStatus || roundStatus.state_name !== 'betting') {
    //   unmet.push('Betting is not available right now.')
    // }
    if (getTotalMultiplier() <= 0) {
      unmet.push('Please select at least one bet multiplier.')
    }
    if (isPlacingBet) {
      unmet.push('A bet is already being placed. Please wait.')
    }
    const betAmount = getTotalBetAmount()
    if (betAmount <= 0) {
      unmet.push('Please set a valid bet amount.')
    }
    // Check contract address validity as part of unmet conditions
    if (!contractService.hasValidContractAddress()) {
      unmet.push('No valid Lottery contract address')
    }

    if (unmet.length > 0) {
      setUnmetConditions(unmet)
      setDialogOpen(true)
      return false
    }

  setIsPlacingBet(true)
  // clear any existing notification
  setNotificationOpen(false)
  setNotificationMessage('')
  setNotificationSeverity('info')

    try {
      // Place bet directly via smart contract
      const transactionHash = await contractService.placeBet(betAmount.toString())

      // Optimistically update UI and show success dialog
      const successMsg = `Bet placed successfully! Transaction: ${transactionHash.slice(0, 10)}...`
      setNotificationMessage(successMsg)
      setNotificationSeverity('success')
      setNotificationOpen(true)
      setUserBetAmount(prev => prev + betAmount)
      
      // Notify backend for verification (optional)
      try {
        await api.post('/api/verify-bet', {
          user_address: address,
          transaction_hash: transactionHash,
          draw_id: roundStatus ? roundStatus.round_id : ''
        })
      } catch (err) {
        console.warn('Backend verification failed:', err)
      }
      // Refresh current draw
      fetchRoundStatus()
    } catch (err: any) {
      const msg = err?.message || 'Bet failed'
      setNotificationMessage(msg)
      setNotificationSeverity('error')
      setNotificationOpen(true)
    } finally {
      setIsPlacingBet(false)
    }
    return true
  }

  // Bet button is always enabled, checks moved to handlePlaceBet

  const MultiplierControl: React.FC<{
    label: string
    value: number
    onChange: (value: number) => void
    max?: number
    disabled?: boolean
  }> = ({ label, value, onChange, max = 99, disabled = false }) => (
    <Box sx={{ 
      display: 'flex', 
      flexDirection: 'column', 
      alignItems: 'center',
      minWidth: '60px',
      p: 1,
      background: disabled ? 'rgba(255, 255, 255, 0.05)' : 'rgba(255, 255, 255, 0.1)',
      borderRadius: 1,
      border: '1px solid rgba(255, 255, 255, 0.2)',
      opacity: disabled ? 0.5 : 1
    }}>
      <Typography variant="caption" sx={{ color: 'white', mb: 0.5 }}>
        {label}
      </Typography>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        <IconButton
          size="small"
          onClick={() => onChange(Math.max(0, value - 1))}
          disabled={disabled || value <= 0}
          sx={{ color: 'white', minWidth: '20px', width: '20px', height: '20px' }}
        >
          <Remove fontSize="small" />
        </IconButton>
        <Typography variant="body2" sx={{ 
          color: 'white', 
          minWidth: '20px', 
          textAlign: 'center',
          fontWeight: 'bold'
        }}>
          {value}
        </Typography>
        <IconButton
          size="small"
          onClick={() => onChange(Math.min(max, value + 1))}
          disabled={disabled || value >= max}
          sx={{ color: 'white', minWidth: '20px', width: '20px', height: '20px' }}
        >
          <Add fontSize="small" />
        </IconButton>
      </Box>
    </Box>
  )

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', p: 2, gap: 2 }}>
      {/* First Row - Status */}
      <Box sx={{ 
        display: 'flex', 
        justifyContent: 'center',
        alignItems: 'center',
        p: 2,
        background: 'rgba(255, 255, 255, 0.1)',
        borderRadius: 1,
        border: '1px solid rgba(255, 255, 255, 0.2)'
      }}>
        <Box sx={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          <Typography variant="body2" sx={{ color: 'white' }}>
            Betting Status: <span style={{ 
              color: userBetAmount > 0 ? '#4CAF50' : 'rgba(255, 255, 255, 0.7)',
              fontWeight: 'bold'
            }}>
              {userBetAmount > 0 ? `${userBetAmount.toFixed(4)} ETH` : 'No Bet'}
            </span>
          </Typography>
          
          <Typography variant="body2" sx={{ color: 'white' }}>
            Win Rate: <span style={{ 
              color: calculateWinRate() > 0 ? '#2196F3' : 'rgba(255, 255, 255, 0.7)',
              fontWeight: 'bold'
            }}>
              {calculateWinRate().toFixed(1)}%
            </span>
          </Typography>
        </Box>
      </Box>

      {/* Second Row - Actions */}
      <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
        {/* Left side - Wallet Connection */}
        <Box sx={{ minWidth: '200px' }}>
          <WalletConnection />
        </Box>
        
        {/* Right side - Betting Controls */}
        <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>          
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
            {/* Base Amount Display */}
            <Box sx={{ 
              p: 1,
              background: 'rgba(255, 255, 255, 0.1)',
              borderRadius: 1,
              border: '1px solid rgba(255, 255, 255, 0.2)',
              minWidth: '80px',
              textAlign: 'center',
              opacity: 1
            }}>
              <Typography variant="caption" sx={{ color: 'white' }}>
                Base Bet
              </Typography>
                <Typography variant="body2" sx={{ color: 'white', fontWeight: 'bold' }}>
                  {(minBetAmount ?? BASE_BET)} ETH
                </Typography>
            </Box>

            {/* Multipliers */}
            <MultiplierControl
              label="1x"
              value={ones}
              onChange={setOnes}
              max={99}
            />
            
            <MultiplierControl
              label="10x"
              value={tens}
              onChange={setTens}
              max={9}
            />
            
            <MultiplierControl
              label="100x"
              value={hundreds}
              onChange={setHundreds}
              max={9}
            />

            {/* Bet Button */}
            <Button
              variant="contained"
              onClick={handlePlaceBet}
              startIcon={isPlacingBet ? <CircularProgress size={16} /> : <Casino />}
              sx={{ 
                background: isPlacingBet
                  ? 'rgba(76, 175, 80, 0.3)'
                  : 'linear-gradient(135deg, #4CAF50 0%, #81C784 100%)',
                '&:hover': { background: 'linear-gradient(135deg, #66BB6A 0%, #A5D6A7 100%)' },
                minWidth: '100px',
                height: '56px',
                opacity: isPlacingBet ? 0.6 : 1
              }}
            >
              {isPlacingBet
                ? 'Betting...'
                : `Bet ${getTotalBetAmount().toFixed(2)} ETH`}
            </Button>
          </Box>
        </Box>
      </Box>

      {/* Notification Dialog (replaces inline alerts) */}
      <Dialog open={notificationOpen} onClose={() => setNotificationOpen(false)}>
        <Box sx={{ p: 2, minWidth: 320 }}>
          <Alert severity={notificationSeverity} onClose={() => setNotificationOpen(false)}>
            {notificationMessage}
          </Alert>
        </Box>
      </Dialog>

      {/* Unmet Conditions Dialog */}
      <Box>
        <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)}>
          <Box sx={{ p: 3, minWidth: 320 }}>
            <Typography variant="h6" sx={{ mb: 2 }}>
              Unable to Place Bet
            </Typography>
            <Typography variant="body2" sx={{ mb: 1 }}>
              Please resolve the following issues:
            </Typography>
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              {unmetConditions.map((cond, idx) => (
                <li key={idx} style={{ color: '#d32f2f', marginBottom: 8 }}>
                  {cond}
                </li>
              ))}
            </ul>
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 2 }}>
              <Button variant="contained" color="primary" onClick={() => setDialogOpen(false)}>
                OK
              </Button>
            </Box>
          </Box>
        </Dialog>
      </Box>
    </Box>
  )
}

export default BettingPanel