import { useEffect, useState } from 'react'

import { fetchDatabaseInfo, fetchReviewers } from './api/client'
import type { DatabaseInfo, Reviewer } from './api/types'
import { ModeBanner } from './components/ModeBanner'
import { RoadmapNote } from './components/RoadmapNote'
import { SoonBadge } from './components/StateBadge'
import { ROADMAP_NOTES } from './domain/vocabulary'
import { navigate, useRoute } from './navigation'
import { DashboardScreen } from './screens/DashboardScreen'
import { ImportsScreen } from './screens/ImportsScreen'
import { RealRecordDetailScreen } from './screens/RealRecordDetailScreen'
import { RealRecordListScreen } from './screens/RealRecordListScreen'
import { RecordDetailScreen } from './screens/RecordDetailScreen'
import { RecordListScreen } from './screens/RecordListScreen'
import { SourcesScreen } from './screens/SourcesScreen'

interface NavItem {
  readonly id: string
  readonly label: string
  /** Un módulo no disponible se anuncia, no se oculta: forma parte de la visión. */
  readonly available: boolean
  readonly note?: keyof typeof ROADMAP_NOTES
}

const NAV: readonly NavItem[] = [
  { id: 'inicio', label: 'Inicio', available: true },
  { id: 'registros', label: 'Fichas técnicas', available: true },
  { id: 'fuentes', label: 'Fuentes', available: true },
  { id: 'importaciones', label: 'Importaciones', available: true },
  { id: 'fichas', label: 'Revisión (DEMO)', available: true },
  { id: 'validaciones', label: 'Validaciones', available: false, note: 'dobleValidacion' },
  { id: 'auditoria', label: 'Historial / Auditoría', available: false, note: 'auditoria' },
  { id: 'configuracion', label: 'Configuración', available: false, note: 'exportacion' },
]

function activeNavId(routeName: string, routeId: string | null): string {
  if (routeName === 'ficha' || routeName === 'fichas') return 'fichas'
  if (routeName === 'registro' || routeName === 'registros') return 'registros'
  if (routeName === 'fuentes') return 'fuentes'
  if (routeName === 'importaciones') return 'importaciones'
  if (routeName === 'seccion' && routeId) return routeId
  return 'inicio'
}

function PlaceholderScreen({ item }: { item: NavItem }) {
  return (
    <div className='screen'>
      <div className='screen__head'>
        <div>
          <p className='eyebrow'>Módulo previsto</p>
          <h1>
            {item.label} <SoonBadge />
          </h1>
          <p className='lede'>
            Este módulo forma parte de la visión del producto y todavía no está desarrollado. Su
            lugar en la interfaz ya está reservado.
          </p>
        </div>
      </div>
      {item.note && <RoadmapNote title={item.label} note={ROADMAP_NOTES[item.note]} />}
    </div>
  )
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
      <aside className='sidebar'>
        <div className='brand'>
          <span className='brand__mark' aria-hidden='true'>
            F
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
                  <span>{item.label}</span>
                  {!item.available && <SoonBadge label='Pronto' />}
                </button>
              </li>
            ))}
          </ul>
        </nav>
        <p className='sidebar__foot'>Piloto interno · sin datos de pacientes</p>
      </aside>

      <div className='main'>
        <header className='topbar'>
          <p className='topbar__context'>
            Validador de fichas técnicas
            {database && (
              <span className={`mode-chip mode-chip--${database.mode}`}>
                {database.mode === 'real' ? 'REAL' : 'DEMO'}
              </span>
            )}
          </p>
          <label className='field field--inline'>
            <span className='field__label'>Revisor</span>
            <select
              aria-label='Revisor que firma las decisiones'
              value={reviewerId}
              onChange={(event) => {
                const identifier = event.target.value
                setReviewerId(identifier)
                if (identifier) localStorage.setItem('farmalidacion.reviewer', identifier)
                else localStorage.removeItem('farmalidacion.reviewer')
              }}
            >
              <option value=''>Sin revisor seleccionado</option>
              {reviewers.map((item) => (
                <option key={item.identifier} value={item.identifier}>
                  {item.display_name}
                </option>
              ))}
            </select>
          </label>
        </header>

        <main className='content'>
          <ModeBanner info={database} />
          {route.name === 'inicio' && <DashboardScreen />}
          {route.name === 'registros' && <RealRecordListScreen />}
          {route.name === 'registro' && <RealRecordDetailScreen recordId={route.id} />}
          {route.name === 'fuentes' && <SourcesScreen />}
          {route.name === 'importaciones' && <ImportsScreen />}
          {route.name === 'fichas' && <RecordListScreen />}
          {route.name === 'ficha' && (
            <RecordDetailScreen recordId={route.id} reviewer={reviewer} />
          )}
          {route.name === 'seccion' && (
            <PlaceholderScreen
              item={NAV.find((item) => item.id === route.id) ?? NAV[0]}
            />
          )}
        </main>
      </div>
    </div>
  )
}
