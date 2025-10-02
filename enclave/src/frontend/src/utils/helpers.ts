export const formatAddress = (address: string): string => {
  if (!address) return ''
  return `${address.slice(0, 8)}...${address.slice(-4)}`
}

export const formatEther = (wei: string | number | undefined): string => {
  const value = Number(wei ?? 0)
  if (!Number.isFinite(value)) return '0.0000'
  return (value / 1e18).toFixed(4)
}

export const formatTime = (timestamp: string | number): string => {
    const value = Number(timestamp ?? 0)
    if (!Number.isFinite(value) || value <= 0) return ''

    // Convert Unix timestamp (seconds) to Date object
    const date = new Date(value * 1000)

    // Format in user's local timezone and locale
    try {
      return new Intl.DateTimeFormat(undefined, {
        year: 'numeric',
        month: 'short',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
      }).format(date)
    } catch (error) {
      // Fallback if Intl formatting fails
      return date.toLocaleString()
    }
}

export const formatTimeAgo = (timestamp: string): string => {
  const date = new Date(timestamp)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSecs = Math.floor(diffMs / 1000)
  const diffMins = Math.floor(diffSecs / 60)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffSecs < 60) {
    return 'Just now'
  } else if (diffMins < 60) {
    return `${diffMins}m ago`
  } else if (diffHours < 24) {
    return `${diffHours}h ago`
  } else if (diffDays < 7) {
    return `${diffDays}d ago`
  } else {
    return formatTime(timestamp)
  }
}

export const generateAvatarColor = (seed: string): string => {
  const colors = [
    '#f44336', '#e91e63', '#9c27b0', '#673ab7',
    '#3f51b5', '#2196f3', '#03a9f4', '#00bcd4',
    '#009688', '#4caf50', '#8bc34a', '#cddc39',
    '#ffeb3b', '#ffc107', '#ff9800', '#ff5722',
    '#795548', '#9e9e9e', '#607d8b', '#ff4081',
    '#7c4dff', '#536dfe', '#448aff', '#18ffff',
    '#64ffda', '#69f0ae', '#b2ff59', '#eeff41',
    '#ffff00', '#ffd740', '#ffab40', '#ff6e40'
  ]
  
  const index = parseInt(seed.slice(-4), 32) % colors.length
  return colors[index]
}

export const copyToClipboard = async (text: string): Promise<boolean> => {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch (error) {
    // Fallback for older browsers
    const textArea = document.createElement('textarea')
    textArea.value = text
    textArea.style.position = 'fixed'
    textArea.style.left = '-999999px'
    textArea.style.top = '-999999px'
    document.body.appendChild(textArea)
    textArea.focus()
    textArea.select()
    
    try {
      document.execCommand('copy')
      textArea.remove()
      return true
    } catch (err) {
      textArea.remove()
      return false
    }
  }
}

export const isValidEthereumAddress = (address: string): boolean => {
  return /^0x[a-fA-F0-9]{40}$/.test(address)
}

export const calculateWinChance = (userTickets: number, totalTickets: number): number => {
  if (totalTickets === 0) return 0
  return (userTickets / totalTickets) * 100
}