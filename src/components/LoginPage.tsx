import { useState } from 'react'
import { motion } from 'framer-motion'
import { MapPin, ShieldAlert, Loader2 } from 'lucide-react'
import { api, setToken } from '../lib/api'

interface Props {
  onLogin: () => void
}

export default function LoginPage({ onLogin }: Props) {
  const [username, setUsername] = useState('sih')
  const [password, setPassword] = useState('sih2026')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await api.login(username, password)
      setToken(res.token)
      onLogin()
    } catch (err) {
      setError((err as Error).message || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="h-screen flex items-center justify-center bg-surface-900 relative overflow-hidden">
      <div
        className="absolute inset-0 animate-gradient"
        style={{
          background:
            'radial-gradient(600px 400px at 20% 30%, rgba(99,102,241,0.15), transparent), radial-gradient(600px 400px at 80% 70%, rgba(6,182,212,0.12), transparent), radial-gradient(500px 300px at 60% 20%, rgba(139,92,246,0.1), transparent)',
        }}
      />

      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="relative w-full max-w-md mx-4"
      >
        <div className="gradient-border glass rounded-2xl p-8 glow-accent">
          <div className="flex items-center justify-center mb-6 gap-3">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-accent-500 to-cyan-500 flex items-center justify-center">
              <ShieldAlert className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight">
                Red Zone Intelligence
              </h1>
              <p className="text-sm text-slate-400">
                Multi-Hazard Relocation Platform · SIH 2026
              </p>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm text-slate-400 mb-1.5">Username</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full px-4 py-2.5 rounded-lg bg-surface-800 border border-surface-600 text-white focus:border-accent-500 focus:outline-none transition"
                placeholder="Enter username"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-1.5">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-2.5 rounded-lg bg-surface-800 border border-surface-600 text-white focus:border-accent-500 focus:outline-none transition"
                placeholder="Enter password"
              />
            </div>

            {error && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="text-sm text-rose-400 bg-rose-500/10 border border-rose-500/20 rounded-lg px-3 py-2"
              >
                {error}
              </motion.div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded-lg bg-gradient-to-r from-accent-500 to-accent-600 text-white font-medium hover:opacity-90 transition flex items-center justify-center gap-2 disabled:opacity-60"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <MapPin className="w-4 h-4" />}
              Sign In
            </button>
          </form>

          <p className="text-xs text-slate-500 mt-5 text-center">
            Demo credentials: <span className="text-slate-300">sih / sih2026</span>
          </p>
        </div>
      </motion.div>
    </div>
  )
}