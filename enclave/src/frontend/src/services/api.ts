import axios from 'axios'

// Prefer Vite-style env var, then CRA-style REACT_APP env, then same-origin in production,
// otherwise fall back to the old hardcoded host used in development.
const VITE_API = (import.meta.env as any).VITE_API_BASE_URL
const API_BASE_URL = VITE_API

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
  const response = await api.get('/api/round/status')
  return response.data
}

// Get current participants
export const getParticipants = async () => {
  const response = await api.get('/api/round/participants')
  return response.data
}

// Get lottery history with pagination
export const getLotteryHistory = async (limit: number = 50) => {
  const response = await api.get('/api/history', {
    params: { limit }
  })
  return response.data
}

// Get recent activities
export const getActivities = async () => {
  const response = await api.get('/api/activities')
  return response.data
}

// Get lottery contract configuration and address
export const getContractConfig = async () => {
  const response = await api.get('/api/contract/config')
  return response.data
}

// Get only the configured lottery contract address
export const getContractAddress = async () => {
  const response = await api.get('/api/contract/address')
  return response.data
}

export default api