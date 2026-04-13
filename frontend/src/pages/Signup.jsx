import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useAuth } from '../context/AuthContext'
import Input from '../components/ui/Input'
import Button from '../components/ui/Button'

export default function Signup() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const { loginUser } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = (e) => {
    e.preventDefault()
    loginUser({ name, email })
    navigate('/dashboard')
  }

  return (
    <div className="min-h-screen bg-bg-base flex items-center justify-center px-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-[400px]"
      >
        <div className="text-center mb-8">
          <div className="w-10 h-10 rounded-xl bg-accent flex items-center justify-center text-[#080808] font-bold text-lg mx-auto mb-4">S</div>
          <h1 className="t-h2 text-text-1">create your account</h1>
          <p className="text-text-2 text-sm mt-2">start protecting your identity documents</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <Input label="name" placeholder="your name" value={name} onChange={e => setName(e.target.value)} required />
          <Input label="email" type="email" placeholder="you@example.com" value={email} onChange={e => setEmail(e.target.value)} required />
          <Input label="password" type="password" placeholder="••••••••" value={password} onChange={e => setPassword(e.target.value)} required />
          <Button type="submit" className="w-full mt-2">create account</Button>
        </form>

        <p className="text-text-3 text-sm text-center mt-6">
          already have an account?{' '}
          <Link to="/login" className="text-accent hover:text-accent-hover">sign in</Link>
        </p>
      </motion.div>
    </div>
  )
}
