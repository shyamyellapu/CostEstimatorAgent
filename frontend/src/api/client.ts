import axios from 'axios'

// Use relative URL in dev so Vite proxy handles requests (no CORS).
// Use absolute URL in production (VITE_BACKEND_URL set at build time).
const _backendUrl = import.meta.env.VITE_BACKEND_URL
const API_BASE_URL = (_backendUrl && !_backendUrl.startsWith('http://127') && !_backendUrl.startsWith('http://localhost'))
  ? `${_backendUrl}/api`
  : '/api'

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.response.use(
  res => res,
  err => {
    const msg = err.response?.data?.detail || err.message || 'An error occurred'
    return Promise.reject(new Error(msg))
  }
)
