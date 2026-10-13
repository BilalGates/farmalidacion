import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './App'
import { AccessGate } from './auth/AccessGate'
import './styles.css'
import './studio.css'

const root = document.getElementById('root')

if (!root) throw new Error('No se encontró el contenedor principal.')

createRoot(root).render(
  <StrictMode>
    <AccessGate><App /></AccessGate>
  </StrictMode>,
)
