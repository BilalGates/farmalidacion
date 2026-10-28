import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './App'
import { AccessGate } from './auth/AccessGate'
import './ui/tokens.css'
import './styles.css'
import './studio.css'
import './ui/components.css'
// Hojas de pantalla migradas: tras los componentes para prevalecer sobre las históricas.
import './screens/catalog.css'
import './screens/work.css'
import './screens/sources.css'
import './screens/review.css'

const root = document.getElementById('root')

if (!root) throw new Error('No se encontró el contenedor principal.')

createRoot(root).render(
  <StrictMode>
    <AccessGate><App /></AccessGate>
  </StrictMode>,
)
