import { useEffect, useState } from 'react'
import {
  Database,
  FileStack,
  History,
  Home,
  ListChecks,
  Upload,
  Users,
  type LucideIcon,
} from 'lucide-react'

import { fetchDashboard, fetchDatabaseInfo, fetchReviewers } from './api/client'
import type { DatabaseInfo, Reviewer } from './api/types'
import { useQuery } from './api/useQuery'
import { ModeBanner } from './components/ModeBanner'
import { ReviewerSelect } from './components/ReviewerSelect'
import { SectionWorkspace } from './components/SectionWorkspace'
import { formatDateTime } from './domain/format'
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
import { CatalogIdentityScreen } from './screens/CatalogIdentityScreen'
import { QuarantinedRecordsScreen } from './screens/QuarantinedRecordsScreen'

interface NavItem {
  readonly id: string
  readonly label: string
  readonly icon: LucideIcon
  /** Un módulo no disponible se anuncia, no se oculta: forma parte de la visión. */
  readonly available: boolean
  readonly path: string
}

function NavIcon({ icon: Icon }: { readonly icon: LucideIcon }) {
  return <Icon className='nav__icon' aria-hidden='true' strokeWidth={1.8} />
}

/**
 * Menú de la aplicación.
 *
 * Las pantallas relacionadas comparten sección; Catálogo y Novedades CIMA son
 * destinos separados porque atienden tareas distintas.
 */
const NAV: readonly NavItem[] = [
  { id: 'inicio', label: 'Inicio', icon: Home, available: true, path: '/' },
  { id: 'fichas', label: 'Catálogo', icon: FileStack, available: true, path: '/fichas' },
  { id: 'novedades', label: 'Novedades CIMA', icon: History, available: true, path: '/novedades' },
  { id: 'revision', label: 'Revisión', icon: ListChecks, available: true, path: '/revision/cola' },
  { id: 'datos', label: 'Datos', icon: Database, available: true, path: '/datos/fuentes' },
  { id: 'exportaciones', label: 'Exportaciones', icon: Upload, available: true, path: '/exportaciones' },
  { id: 'revisores', label: 'Revisores', icon: Users, available: true, path: '/revisores' },
]

function activeNavId(routeName: string, routeId: string | null): string {
  if (routeName === 'ficha' || routeName === 'fichas' || routeName === 'catalogo') return 'fichas'
  if (routeName === 'fuentes' || routeName === 'importaciones') return 'datos'
  if (routeName === 'seccion' && routeId === 'catalogo/novedades') return 'novedades'
  if (routeName === 'seccion' && routeId?.startsWith('revision/')) return 'revision'
  if (routeName === 'seccion' && routeId?.startsWith('datos/')) return 'datos'
  if (routeName === 'seccion' && routeId) return routeId
  return 'inicio'
}

export function App() {
  const route = useRoute()
  const { data: dashboard } = useQuery(() => fetchDashboard(), [])
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
      {/* La navegación principal agrupa páginas por recorrido. */}
      <header className='topbar'>
        <div className='brand'>
          <img className='brand__mark' src='/brand-mark.svg' alt='' aria-hidden='true' />
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
                  onClick={() => navigate(item.path)}
                >
                  <NavIcon icon={item.icon} />
                  <span>{item.label}</span>
                </button>
              </li>
            ))}
          </ul>
        </nav>

        <div className='topbar__actions'>
          <div className='dashboard-freshness dashboard-freshness--topbar'>
            <span className='dashboard-freshness__dot' aria-hidden='true' />
            <span>
              <strong>Datos actualizados</strong>
              <small>
                {dashboard?.last_import_at
                  ? formatDateTime(dashboard.last_import_at)
                  : 'Sin importaciones'}
              </small>
            </span>
          </div>
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
          {route.name === 'fichas' && (
            <RealRecordListScreen />
          )}
          {route.name === 'ficha' && (
            <ReviewScreen key={route.id} recordId={route.id} reviewer={reviewer} />
          )}
          {route.name === 'catalogo' && (
            <CatalogIdentityScreen key={route.id} identityId={route.id} reviewer={reviewer} />
          )}
          {route.name === 'fuentes' && (
            <SectionWorkspace group='data' active='sources'><SourcesScreen /></SectionWorkspace>
          )}
          {route.name === 'importaciones' && (
            <SectionWorkspace group='data' active='imports'><ImportsScreen /></SectionWorkspace>
          )}
          {route.name === 'seccion' && route.id === 'datos/cuarentena' && (
            <SectionWorkspace group='data' active='quarantine'><QuarantinedRecordsScreen reviewer={reviewer} /></SectionWorkspace>
          )}
          {route.name === 'seccion' && route.id === 'revision/cola' && (
            <SectionWorkspace group='review' active='queue'><QueueScreen reviewer={reviewer} /></SectionWorkspace>
          )}
          {route.name === 'seccion' && route.id === 'revision/validaciones' && (
            <SectionWorkspace group='review' active='second-review'><SecondReviewScreen reviewer={reviewer} /></SectionWorkspace>
          )}
          {route.name === 'seccion' && route.id === 'exportaciones' && (
            <ExportsScreen reviewer={reviewer} />
          )}
          {route.name === 'seccion' && route.id === 'catalogo/novedades' && (
            <MaintenanceScreen />
          )}
          {route.name === 'seccion' && route.id === 'revisores' && <ReviewersScreen />}
        </main>
      </div>
    </div>
  )
}
