import axios from 'axios'

const API_BASE_URL = import.meta.env.MODE === 'production' 
  ? '' // Same origin in production
  : 'http://localhost:6080'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
})

// Request interceptor
api.interceptors.request.use((config) => {
  // Add any auth headers here if needed
  return config
})

// Response interceptor
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message)
    return Promise.reject(error)
  }
)

// Health check
export const getHealth = async () => {
  const response = await api.get('/api/health')
  return response.data
}

// Enclave attestation
export const getAttestation = async () => {
  const response = await api.get('/api/attestation')
  return response.data
}

// Current draw information
export const getCurrentDraw = async () => {
  const response = await api.get('/api/draw/current')
  return response.data
}

// Get current participants
export const getParticipants = async () => {
  const response = await api.get('/api/draw/participants')
  return response.data
}

// Get lottery history
export const getLotteryHistory = async () => {
  const response = await api.get('/api/history')
  return response.data
}

// Get recent activities
export const getActivities = async () => {
  const response = await api.get('/api/activities')
  return response.data
}

// Get lottery contract address and network
export const getLotteryContract = async () => {
  const response = await api.get('/api/lottery/contract')
  return response.data
}

// Connect wallet
export const connectWallet = async (address: string, signature: string) => {
  const response = await api.post('/api/auth/connect', {
    address,
    signature,
  })
  return response.data
}

// Place bet
export const placeBet = async (betData: {
  user_address: string
  amount: number
  transaction_hash: string
}) => {
  const response = await api.post('/api/bet', betData)
  return response.data
}

export default api