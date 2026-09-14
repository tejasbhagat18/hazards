import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'

if (import.meta.env.DEV && new URLSearchParams(window.location.search).has('autologin')) {
  localStorage.setItem('sih_token', 'demo-token-sih')
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
