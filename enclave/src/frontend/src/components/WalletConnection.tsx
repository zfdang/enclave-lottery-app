import React, { useState } from 'react'
import {
  Button,
  Typography,
  Box,
  Avatar,
  Menu,
  MenuItem,
  Divider,
  Alert,
} from '@mui/material'
import { 
  AccountBalanceWallet, 
  ExpandMore,
  ContentCopy,
  ExitToApp
} from '@mui/icons-material'

import { useWalletStore } from '../services/wallet'

const WalletConnection: React.FC = () => {
  const { 
    isConnected, 
    address, 
    balance, 
    connect, 
    disconnect,
    isConnecting 
  } = useWalletStore()
  
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null)
  const [error, setError] = useState('')

  const handleConnect = async () => {
    try {
      setError('')
      await connect()
    } catch (err: any) {
      setError(err.message || 'Failed to connect wallet')
    }
  }

  const handleDisconnect = () => {
    disconnect()
    setAnchorEl(null)
  }

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget)
  }

  const handleMenuClose = () => {
    setAnchorEl(null)
  }

  const copyAddress = () => {
    if (address) {
      navigator.clipboard.writeText(address)
    }
    handleMenuClose()
  }

  const formatAddress = (addr: string): string => {
    return `${addr.slice(0, 6)}...${addr.slice(-4)}`
  }

  const formatBalance = (bal: string): string => {
    const num = parseFloat(bal)
    return num.toFixed(4)
  }

  const getAvatarColor = (addr: string): string => {
    const colors = [
      '#f44336', '#e91e63', '#9c27b0', '#673ab7',
      '#3f51b5', '#2196f3', '#03a9f4', '#00bcd4',
      '#009688', '#4caf50', '#8bc34a', '#cddc39',
      '#ffeb3b', '#ffc107', '#ff9800', '#ff5722'
    ]
    const index = parseInt(addr.slice(-2), 16) % colors.length
    return colors[index]
  }

  if (!isConnected) {
    return (
      <Box>
        <Button
          variant="contained"
          startIcon={<AccountBalanceWallet />}
          onClick={handleConnect}
          disabled={isConnecting}
          sx={{
            borderRadius: 2,
            textTransform: 'none',
            fontWeight: 600,
          }}
        >
          {isConnecting ? 'Connecting...' : 'Connect Wallet'}
        </Button>
        
        {error && (
          <Alert severity="error" sx={{ mt: 1, maxWidth: 300 }}>
            {error}
          </Alert>
        )}
      </Box>
    )
  }

  return (
    <Box>
      <Button
        variant="outlined"
        endIcon={<ExpandMore />}
        onClick={handleMenuOpen}
        sx={{
          borderRadius: 2,
          textTransform: 'none',
          fontWeight: 600,
          color: 'white',
          borderColor: 'rgba(255, 255, 255, 0.3)',
          '&:hover': {
            borderColor: 'rgba(255, 255, 255, 0.5)',
            backgroundColor: 'rgba(255, 255, 255, 0.1)',
          },
        }}
      >
        <Avatar 
          sx={{ 
            bgcolor: address ? getAvatarColor(address) : 'primary.main',
            width: 24, 
            height: 24,
            mr: 1,
            fontSize: '0.75rem'
          }}
        >
          {address ? address.slice(2, 4).toUpperCase() : 'W'}
        </Avatar>
        <Box textAlign="left">
          <Typography variant="body2" fontWeight="bold">
            {address ? formatAddress(address) : 'Wallet'}
          </Typography>
          {balance && (
            <Typography variant="caption" color="rgba(255, 255, 255, 0.7)">
              {formatBalance(balance)} ETH
            </Typography>
          )}
        </Box>
      </Button>

      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'right',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'right',
        }}
        PaperProps={{
          sx: {
            mt: 1,
            minWidth: 250,
            backdropFilter: 'blur(10px)',
            backgroundColor: 'rgba(0, 0, 0, 0.8)',
            border: '1px solid rgba(255, 255, 255, 0.2)',
          },
        }}
      >
        <Box px={2} py={1}>
          <Typography variant="caption" color="text.secondary">
            Connected Account
          </Typography>
          <Typography variant="body2" fontFamily="monospace" sx={{ wordBreak: 'break-all' }}>
            {address}
          </Typography>
          {balance && (
            <Typography variant="body2" color="primary.main" fontWeight="bold">
              {formatBalance(balance)} ETH
            </Typography>
          )}
        </Box>
        
        <Divider />
        
        <MenuItem onClick={copyAddress}>
          <ContentCopy sx={{ mr: 2 }} />
          Copy Address
        </MenuItem>
        
        <Divider />
        
        <MenuItem onClick={handleDisconnect}>
          <ExitToApp sx={{ mr: 2 }} />
          Disconnect
        </MenuItem>
      </Menu>
    </Box>
  )
}

export default WalletConnection