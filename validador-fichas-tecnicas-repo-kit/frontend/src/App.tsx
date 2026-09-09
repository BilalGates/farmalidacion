import { useEffect, useState } from 'react'
import {
  BadgeCheck,
  Database,
  Download,
  FileStack,
  History,
  Home,
  ListChecks,
  Upload,
  Users,
  type LucideIcon,
} from 'lucide-react'

import { fetchDatabaseInfo, fetchReviewers } from './api/client'
import type { DatabaseInfo, Reviewer } from './api/types'
import { ModeBanner } from './components/ModeBanner'
import { ReviewerSelect } from './components/ReviewerSelect'
import { navigate, useRoute } from './navigation'
import { DashboardScreen } from './screens/DashboardScreen'
import { ImportsScreen } from './screens/ImportsScreen'
import { RealRecordListScreen } from './screens/RealRecordListScreen'
import { ReviewersScreen } from './screens/ReviewersScreen'
import { ReviewScreen } from './screens/ReviewScreen'
import { SourcesScreen } from './screens/SourcesScreen'
import { ExportsScreen } from './screens/ExportsScreen'
import { QueueScreen } from './screens/QueueScreen'
import { SecondReviewScreen } from './screens/SecondReviewScreen'
import { MaintenanceScreen } from './screens/MaintenanceScreen'

interface NavItem {
  readonly id: string
  readonly label: string
  readonly icon: LucideIcon
  /** Un módulo no disponible se anuncia, no se oculta: forma parte de la visión. */
  readonly available: boolean
}

function NavIcon({ icon: Icon }: { readonly icon: LucideIcon }) {
  return <Icon className='nav__icon' aria-hidden='true' strokeWidth={1.8} />
}

/**
 * Menú de la aplicación.
 *
 * «Fichas técnicas» y «Revisión (DEMO)» eran dos entradas hacia la misma
 * pantalla de detalle, así que se fusionan en «Registros». Las secciones aún no
 * construidas no figuran aquí: un menú que anuncia lo que no existe obliga a
 * descubrir a base de clics qué es real, y el trabajo diario ocurre en una sola
 * pantalla.
 */
const NAV: readonly NavItem[] = [
  { id: 'inicio', label: 'Inicio', icon: Home, available: true },
  { id: 'fichas', label: 'Registros', icon: FileStack, available: true },
  { id: 'cola', label: 'Cola de revisión', icon: ListChecks, available: true },
  { id: 'validaciones', label: 'Validaciones', icon: BadgeCheck, available: true },
  { id: 'importaciones', label: 'Importaciones', icon: Download, available: true },
  { id: 'exportaciones', label: 'Exportaciones', icon: Upload, available: true },
  { id: 'fuentes', label: 'Fuentes', icon: Database, available: true },
  { id: 'novedades', label: 'Novedades CIMA', icon: History, available: true },
  { id: 'revisores', label: 'Revisores', icon: Users, available: true },
]

function activeNavId(routeName: string, routeId: string | null): string {
  if (routeName === 'ficha' || routeName === 'fichas') return 'fichas'
  if (routeName === 'fuentes') return 'fuentes'
  if (routeName === 'importaciones') return 'importaciones'
  if (routeName === 'seccion' && routeId) return routeId
  return 'inicio'
}

export function App() {
  const route = useRoute()
  const [reviewers, setReviewers] = useState<Reviewer[]>([])
  const [reviewerId, setReviewerId] = useState(() => localStorage.getItem('farmalidacion.reviewer') ?? '')
  const [database, setDatabase] = useState<DatabaseInfo | null>(null)

  useEffect(() => {
    fetchReviewers()
      .then(setReviewers)
      .catch(() => setReviewers([]))
  }, [])

  // El modo se consulta una vez al arrancar: no cambia mientras la pestaña vive,
  // porque cambiarlo exige reiniciar el backend contra otra base.
  useEffect(() => {
    fetchDatabaseInfo()
      .then(setDatabase)
      .catch(() => setDatabase(null))
  }, [])

  const reviewer = reviewers.find((item) => item.identifier === reviewerId) ?? null
  const active = activeNavId(route.name, route.name === 'seccion' ? route.id : null)

  return (
    <div className='layout'>
      {/* Una sola barra para todo: marca, navegación, modo y revisor.
          La sidebar repartía la orientación en dos ejes para nueve destinos y
          se llevaba una columna entera de ancho; el trabajo diario ocurre en la
          pantalla, no en el menú. */}
      <header className='topbar'>
        <div className='brand'>
          <span className='brand__mark' aria-hidden='true'>
            <span />
            <span />
          </span>
          <span className='brand__name'>Farmalidación</span>
        </div>

        <nav aria-label='Navegación principal'>
          <ul>
            {NAV.map((item) => (
              <li key={item.id}>
                <button
                  type='button'
                  className={`nav__item${active === item.id ? ' nav__item--active' : ''}`}
                  aria-current={active === item.id ? 'page' : undefined}
                  onClick={() => navigate(item.id === 'inicio' ? '/' : `/${item.id}`)}
                >
                  <NavIcon icon={item.icon} />
                  <span>{item.label}</span>
                </button>
              </li>
            ))}
          </ul>
        </nav>

        <div className='topbar__actions'>
          {/* El modo se queda: distinguir un valor de demostración de uno
              importado es lo que esta vertical no se puede permitir fallar. */}
          {database && (
            <span className={`mode-chip mode-chip--${database.mode}`}>
              {database.mode === 'real' ? 'REAL' : 'DEMO'}
            </span>
          )}
          <ReviewerSelect
            reviewers={reviewers}
            value={reviewerId}
            onChange={(identifier) => {
              setReviewerId(identifier)
              if (identifier) localStorage.setItem('farmalidacion.reviewer', identifier)
              else localStorage.removeItem('farmalidacion.reviewer')
            }}
          />
        </div>
      </header>

      <div className='main'>
        <main className='content'>
          <ModeBanner info={database} />
          {route.name === 'inicio' && <DashboardScreen />}
          {route.name === 'fichas' && <RealRecordListScreen />}
          {route.name === 'ficha' && (
            <ReviewScreen key={route.id} recordId={route.id} reviewer={reviewer} />
          )}
          {route.name === 'fuentes' && <SourcesScreen />}
          {route.name === 'importaciones' && <ImportsScreen />}
          {route.name === 'seccion' && route.id === 'cola' && <QueueScreen reviewer={reviewer} />}
          {route.name === 'seccion' && route.id === 'validaciones' && (
            <SecondReviewScreen reviewer={reviewer} />
          )}
          {route.name === 'seccion' && route.id === 'exportaciones' && <ExportsScreen />}
          {route.name === 'seccion' && route.id === 'novedades' && <MaintenanceScreen />}
          {route.name === 'seccion' && route.id === 'revisores' && <ReviewersScreen />}
        </main>
      </div>
    </div>
  )
}
