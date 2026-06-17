import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_BACKEND_URL
// const API_BASE_URL = import.meta.env.VITE_BACKEND_URL||'https://costestimatorbackend-cdckbnh5gkdsfmgr.centralindia-01.azurewebsites.net'

export const api = axios.create({
  baseURL: `${API_BASE_URL}/api`,
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
