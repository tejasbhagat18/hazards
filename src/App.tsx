import { useState } from 'react'
import LoginPage from './components/LoginPage'
import Dashboard from './components/Dashboard'

export default function App() {
  const [authed, setAuthed] = useState(() => Boolean(localStorage.getItem('sih_token')))

  return authed ? (
    <Dashboard onLogout={() => setAuthed(false)} />
  ) : (
    <LoginPage onLogin={() => setAuthed(true)} />
  )
}