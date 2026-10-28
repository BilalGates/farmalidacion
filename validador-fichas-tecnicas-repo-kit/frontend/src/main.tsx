import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './App'
import { AccessGate } from './auth/AccessGate'
import '@fontsource/ibm-plex-sans/latin-400.css'
import '@fontsource/ibm-plex-sans/latin-500.css'
import '@fontsource/ibm-plex-sans/latin-600.css'
import '@fontsource/newsreader/latin-400.css'
import '@fontsource/newsreader/latin-500.css'
import '@fontsource/ibm-plex-mono/latin-400.css'
import '@fontsource/ibm-plex-mono/latin-500.css'
import './ui/tokens.css'
import './styles.css'
import './studio.css'
import './ui/components.css'
import './ui/shell.css'
import './ui/filters.css'
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
