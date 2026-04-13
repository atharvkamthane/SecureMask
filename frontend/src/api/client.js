import axios from 'axios'
import toast from 'react-hot-toast'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  timeout: 60000,
})

client.interceptors.response.use(
  res => res,
  err => {
    const msg = err.response?.data?.detail || err.message || 'something went wrong'
    toast.error(msg, { style: { background: '#111', color: '#F0EDE6', border: '1px solid #2A2A2A' } })
    return Promise.reject(err)
  }
)

export default client
