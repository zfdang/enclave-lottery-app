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

// Enclave attestation - fetches raw CBOR and parses it
export const getAttestation = async () => {
  // Import cbor-web for parsing CBOR data
  const cbor = await import('cbor-web')

  // Fetch raw binary data
  const response = await api.post('/.well-known/attestation', {}, {
    responseType: 'arraybuffer'
  })

  try {
    // Parse CBOR data
    const cborData = cbor.decode(new Uint8Array(response.data))

    // Check if it's a COSE Sign1 message (array with 4 elements)
    if (Array.isArray(cborData) && cborData.length >= 3) {
      // Extract protected header, unprotected header, payload, signature
      const protectedHeader = cborData[0]
      const unprotectedHeader = cborData[1]
      const payload = cborData[2]
      const signature = cborData.length > 3 ? cborData[3] : null

      // Parse the payload (attestation document)
      const attestationDoc = cbor.decode(payload)

      // Helper function to convert bytes to hex
      const bytesToHex = (bytes: Uint8Array | ArrayBuffer): string => {
        const arr = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes)
        return Array.from(arr).map(b => b.toString(16).padStart(2, '0')).join('')
      }

      // Helper function to convert bytes to base64
      const bytesToBase64 = (bytes: Uint8Array | ArrayBuffer): string => {
        const arr = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes)
        return btoa(String.fromCharCode(...arr))
      }

      // Format PCRs as hex strings
      const pcrs: Record<string, string> = {}
      if (attestationDoc.pcrs) {
        for (const [key, value] of Object.entries(attestationDoc.pcrs)) {
          if (value instanceof Uint8Array || value instanceof ArrayBuffer) {
            pcrs[key] = bytesToHex(value as Uint8Array)
          } else {
            pcrs[key] = String(value)
          }
        }
      }

      // Parse user_data
      let userData = null
      if (attestationDoc.user_data) {
        try {
          if (attestationDoc.user_data instanceof Uint8Array) {
            const decoder = new TextDecoder()
            const userDataStr = decoder.decode(attestationDoc.user_data)
            userData = JSON.parse(userDataStr)
          }
        } catch (e) {
          console.warn('Failed to parse user_data as JSON:', e)
        }
      }

      // Format public key
      let publicKey = null
      if (attestationDoc.public_key instanceof Uint8Array) {
        publicKey = bytesToHex(attestationDoc.public_key)
      }

      return {
        attestation_document: {
          module_id: attestationDoc.module_id,
          timestamp: attestationDoc.timestamp,
          digest: attestationDoc.digest,
          pcrs,
          public_key: publicKey,
          user_data: userData,
          // Note: certificate and cabundle are large, just indicate they exist
          has_certificate: !!attestationDoc.certificate,
          has_cabundle: Array.isArray(attestationDoc.cabundle) && attestationDoc.cabundle.length > 0
        },
        signature: signature ? bytesToHex(signature) : null
      }
    }

    // Fallback: return raw decoded data
    return cborData
  } catch (e) {
    console.error('Failed to parse CBOR attestation:', e)
    throw new Error('Failed to parse attestation data')
  }
}

// Current draw information
export const getRoundStatus = async () => {
  const response = await api.get('/api/round/status')
  return response.data
}

// Backwards-compatible alias for older callers
// alias removed: prefer getRoundStatus

// Get current participants
export const getParticipants = async () => {
  const response = await api.get('/api/round/participants')
  return response.data
}

// Get total amount (wei) a player has bet in the current round
export const getPlayerInfo = async (address: string) => {
  const response = await api.get('/api/round/player', { params: { player: address } })
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