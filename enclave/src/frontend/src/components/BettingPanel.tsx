import React, { useState, useEffect } from 'react'
import {
  Typography,
  Box,
  Button,
  Alert,
  CircularProgress,
  IconButton,
} from '@mui/material'
import { Casino, Add, Remove } from '@mui/icons-material'

import { useWalletStore } from '../services/wallet'
import { useLotteryStore } from '../services/lottery'
import { contractService } from '../services/contract'
import api from '../services/api'
import WalletConnection from './WalletConnection'

const BettingPanel: React.FC = () => {
  const { isConnected, address } = useWalletStore()
  const { currentDraw, fetchCurrentDraw } = useLotteryStore()
  const [isPlacingBet, setIsPlacingBet] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [bettingLimits, setBettingLimits] = useState({ min: '0.01', max: '10', maxBetsPerUser: 10 })
  const [userBetAmount, setUserBetAmount] = useState(0)
  
  // Betting multipliers
  const [ones, setOnes] = useState(1)
  const [tens, setTens] = useState(0)
  const [hundreds, setHundreds] = useState(0)

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
    // Load user's bet amount for current draw
    const loadUserBetAmount = async () => {
      if (currentDraw && address) {
        try {
          const userBets = await contractService.getUserBets(currentDraw.draw_id, address)
          const totalAmount = userBets.reduce((sum: number, bet: any) => sum + parseFloat(bet.amount), 0)
          setUserBetAmount(totalAmount)
        } catch (error) {
          console.error('Failed to load user bet amount:', error)
        }
      }
    }

    loadUserBetAmount()
  }, [currentDraw, address])

  const getTotalMultiplier = (): number => {
    return ones + tens * 10 + hundreds * 100
  }

  const getTotalBetAmount = (): number => {
    return parseFloat(bettingLimits.min) * getTotalMultiplier()
  }

  const calculateWinRate = (): number => {
    if (!currentDraw || !isConnected || userBetAmount === 0) return 0
    const totalPot = parseFloat(currentDraw.total_pot?.toString() || '0')
    const userTickets = userBetAmount / parseFloat(bettingLimits.min)
    const totalTickets = totalPot / parseFloat(bettingLimits.min)
    return totalTickets > 0 ? (userTickets / totalTickets) * 100 : 0
  }

  const handlePlaceBet = async () => {
    if (!isConnected || !address) {
      setError('Please connect your wallet first')
      return
    }

    if (!currentDraw || currentDraw.status !== 'betting') {
      setError('Betting is not available right now')
      return
    }

    const betAmount = getTotalBetAmount()
    if (betAmount <= 0) {
      setError('Please set a valid bet amount')
      return
    }

    setIsPlacingBet(true)
    setError('')
    setSuccess('')

    try {
      // Place bet directly via smart contract
      const transactionHash = await contractService.placeBet(currentDraw.draw_id, betAmount.toString())

      // Optimistically update UI
      setSuccess(`Bet placed successfully! Transaction: ${transactionHash.slice(0, 10)}...`)
      setUserBetAmount(prev => prev + betAmount)
      
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

  const canPlaceBet = (): boolean => {
    return (
      isConnected &&
      currentDraw?.status === 'betting' &&
      getTotalMultiplier() > 0 &&
      !isPlacingBet
    )
  }

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
              background: isConnected ? 'rgba(255, 255, 255, 0.1)' : 'rgba(255, 255, 255, 0.05)',
              borderRadius: 1,
              border: '1px solid rgba(255, 255, 255, 0.2)',
              minWidth: '80px',
              textAlign: 'center',
              opacity: isConnected ? 1 : 0.5
            }}>
              <Typography variant="caption" sx={{ color: 'white' }}>
                Base Bet
              </Typography>
              <Typography variant="body2" sx={{ color: 'white', fontWeight: 'bold' }}>
                {bettingLimits.min} ETH
              </Typography>
            </Box>

            {/* Multipliers */}
            <MultiplierControl
              label="1x"
              value={ones}
              onChange={setOnes}
              max={99}
              disabled={!isConnected}
            />
            
            <MultiplierControl
              label="10x"
              value={tens}
              onChange={setTens}
              max={9}
              disabled={!isConnected}
            />
            
            <MultiplierControl
              label="100x"
              value={hundreds}
              onChange={setHundreds}
              max={9}
              disabled={!isConnected}
            />

            {/* Bet Button */}
            <Button
              variant="contained"
              onClick={handlePlaceBet}
              disabled={!canPlaceBet()}
              startIcon={isPlacingBet ? <CircularProgress size={16} /> : <Casino />}
              sx={{ 
                background: !isConnected 
                  ? 'rgba(128, 128, 128, 0.3)' 
                  : isPlacingBet 
                    ? 'rgba(76, 175, 80, 0.3)' 
                    : 'linear-gradient(135deg, #4CAF50 0%, #81C784 100%)',
                '&:hover': !isConnected 
                  ? { background: 'rgba(128, 128, 128, 0.3)' }
                  : { background: 'linear-gradient(135deg, #66BB6A 0%, #A5D6A7 100%)' },
                minWidth: '100px',
                height: '56px',
                opacity: isConnected ? 1 : 0.6
              }}
            >
              {!isConnected 
                ? 'Connect Wallet' 
                : isPlacingBet 
                  ? 'Betting...' 
                  : `Bet ${getTotalBetAmount().toFixed(2)} ETH`}
            </Button>
          </Box>
        </Box>
      </Box>

      {/* Error and Success Messages */}
      {error && (
        <Alert severity="error" sx={{ fontSize: '0.8rem' }}>
          {error}
        </Alert>
      )}

      {success && (
        <Alert severity="success" sx={{ fontSize: '0.8rem' }}>
          {success}
        </Alert>
      )}
    </Box>
  )
}

export default BettingPanel