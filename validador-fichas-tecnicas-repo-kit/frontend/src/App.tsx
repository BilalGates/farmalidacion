import { useEffect, useState } from 'react'

import { fetchReviewers } from './api/client'
import type { Reviewer } from './api/types'
import { RoadmapNote } from './components/RoadmapNote'
import { SoonBadge } from './components/StateBadge'
import { DEMO_DATA_NOTICE, ROADMAP_NOTES } from './domain/vocabulary'
import { navigate, useRoute } from './navigation'
import { RecordDetailScreen } from './screens/RecordDetailScreen'
import { RecordListScreen } from './screens/RecordListScreen'

interface NavItem {
  readonly id: string
  readonly label: string
  /** Un módulo no disponible se anuncia, no se oculta: forma parte de la visión. */
  readonly available: boolean
  readonly note?: keyof typeof ROADMAP_NOTES
}

const NAV: readonly NavItem[] = [
  { id: 'inicio', label: 'Inicio', available: true },
  { id: 'fichas', label: 'Fichas técnicas', available: true },
  { id: 'validaciones', label: 'Validaciones', available: false, note: 'dobleValidacion' },
  { id: 'fuentes', label: 'Fuentes', available: false, note: 'cima' },
  { id: 'importaciones', label: 'Importaciones', available: false, note: 'importaciones' },
  { id: 'auditoria', label: 'Historial / Auditoría', available: false, note: 'auditoria' },
  { id: 'configuracion', label: 'Configuración', available: false, note: 'exportacion' },
]

function activeNavId(routeName: string, routeId: string | null): string {
  if (routeName === 'ficha' || routeName === 'fichas') return 'fichas'
  if (routeName === 'seccion' && routeId) return routeId
  return 'inicio'
}

function HomeScreen() {
  return (
    <div className='screen'>
      <div className='screen__head'>
        <div>
          <p className='eyebrow'>Farmalidación</p>
          <h1>Consolidación y validación del catálogo</h1>
          <p className='lede'>
            Farmalidación reúne el maestro actual, los metadatos de CIMA y el texto de la ficha
            técnica junto al campo que hay que validar, para que la decisión sea rápida, trazable y
            siempre de una persona identificada.
          </p>
        </div>
      </div>

      <div className='cards'>
        <article className='card'>
          <h2>Qué funciona hoy</h2>
          <ul>
            <li>Listado de registros con estado de revisión y búsqueda.</li>
            <li>Ficha por bloques, con valor, fuente y procedencia de cada campo.</li>
            <li>Detección de discrepancias entre fuentes, sin resolverlas automáticamente.</li>
            <li>Decisión de revisión firmada y persistida como historial.</li>
          </ul>
        </article>
        <article className='card'>
          <h2>Qué llegará después</h2>
          <ul>
            <li>Extracción asistida con evidencia literal verificable.</li>
            <li>Contraste versionado con CIMA.</li>
            <li>Doble validación y conciliación de discrepancias.</li>
            <li>Exportación al sistema destino.</li>
          </ul>
        </article>
      </div>

      <div className='cards'>
        <article className='card card--plain'>
          <h2>Límites del producto</h2>
          <ul className='boundary-list'>
            <li>No procesa datos de pacientes</li>
            <li>No emite recomendaciones clínicas</li>
            <li>No decide valores que requieren criterio profesional</li>
            <li>No oculta conflictos entre fuentes</li>
          </ul>
        </article>
      </div>

      <button type='button' className='button button--primary' onClick={() => navigate('/fichas')}>
        Ir a las fichas técnicas
      </button>
    </div>
  )
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

  useEffect(() => {
    fetchReviewers()
      .then(setReviewers)
      .catch(() => setReviewers([]))
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
          <p className='topbar__context'>Validador de fichas técnicas</p>
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

        <p className='demo-banner'>{DEMO_DATA_NOTICE}</p>

        <main className='content'>
          {route.name === 'inicio' && <HomeScreen />}
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
