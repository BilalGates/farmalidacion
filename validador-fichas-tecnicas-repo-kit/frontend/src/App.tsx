import { useCallback, useEffect, useState } from 'react'
import {
  Database,
  CheckCheck,
  FileStack,
  Home,
  PanelLeftClose,
  PanelLeftOpen,
  Users,
  type LucideIcon,
} from 'lucide-react'

import { fetchDatabaseInfo, fetchReviewers } from './api/client'
import type { DatabaseInfo, Reviewer } from './api/types'
import { ModeBanner } from './components/ModeBanner'
import { AppearancePreferences } from './components/AppearancePreferences'
import { FilterLayoutContext } from './components/FilterLayoutContext'
import { PilotIdentity } from './components/PilotIdentity'
import { TeamDirectory } from './components/TeamDirectory'
import { useCorporateSession } from './auth/SessionContext'
import { SectionWorkspace } from './components/SectionWorkspace'
import { formatDateTime } from './domain/format'
import { readAppearance, saveAppearance, type ReadingDensity, type ThemeChoice } from './domain/appearance'
import { navigate, useRoute } from './navigation'
import { DashboardScreen } from './screens/DashboardScreen'
import { ImportsScreen } from './screens/ImportsScreen'
import { RealRecordListScreen } from './screens/RealRecordListScreen'
import { ReviewersScreen } from './screens/ReviewersScreen'
import { PageHeader } from './components/PageHeader'
import { AccessAdministration } from './components/AccessAdministration'
import { ReviewScreen } from './screens/ReviewScreen'
import { SourcesScreen } from './screens/SourcesScreen'
import { ExportsScreen } from './screens/ExportsScreen'
import { MaintenanceScreen } from './screens/MaintenanceScreen'
import { CatalogIdentityScreen } from './screens/CatalogIdentityScreen'
import { QuarantinedRecordsScreen } from './screens/QuarantinedRecordsScreen'
import { QueueScreen } from './screens/QueueScreen'
import { SecondReviewScreen } from './screens/SecondReviewScreen'

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
 * Tres áreas por tarea; las rutas antiguas mantienen sus destinos.
 */
const NAV: readonly NavItem[] = [
  { id: 'fichas', label: 'Catálogo', icon: FileStack, available: true, path: '/fichas' },
  { id: 'trabajo', label: 'Trabajo', icon: CheckCheck, available: true, path: '/trabajo' },
  { id: 'datos', label: 'Datos', icon: Database, available: true, path: '/datos/fuentes' },
]

function activeNavId(routeName: string, routeId: string | null): string {
  if (routeName === 'ficha' || routeName === 'fichas' || routeName === 'catalogo') return 'fichas'
  if (routeName === 'fuentes' || routeName === 'importaciones') return 'datos'
  if (routeName === 'seccion' && (routeId === 'trabajo' || routeId?.startsWith('revision/') || routeId?.startsWith('catalogo/'))) return 'trabajo'
  if (routeName === 'seccion' && routeId === 'exportaciones') return 'datos'
  if (routeName === 'seccion' && routeId?.startsWith('datos/')) return 'datos'
  if (routeName === 'seccion' && routeId) return routeId
  return 'inicio'
}

export function App() {
  const session = useCorporateSession()
  const may = (capability: string) => !session || session.capabilities.includes(capability)
  const route = useRoute()
  const [reviewers, setReviewers] = useState<Reviewer[]>([])
  const [reviewerId, setReviewerId] = useState(() => localStorage.getItem('farmalidacion.reviewer') ?? '')
  const [database, setDatabase] = useState<DatabaseInfo | null>(null)
  const [theme, setTheme] = useState<ThemeChoice>(() => readAppearance().theme)
  const [density, setDensity] = useState<ReadingDensity>(() => readAppearance().density)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    const saved = localStorage.getItem('farmalidacion.sidebar.collapsed')
    return saved === null ? window.innerWidth <= 900 : saved === 'true'
  })
  const [openFilterPanels, setOpenFilterPanels] = useState<string[]>([])
  const reportFilterOpen = useCallback((id: string, open: boolean) => {
    setOpenFilterPanels(current => open
      ? current.includes(id) ? current : [...current, id]
      : current.includes(id) ? current.filter(item => item !== id) : current)
  }, [])
  const filtersOpen = openFilterPanels.length > 0
  const navigationCollapsed = sidebarCollapsed || filtersOpen

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

  useEffect(() => {
    const media = window.matchMedia?.('(prefers-color-scheme: dark)')
    const apply = () => {
      const dark = theme === 'dark' || (theme === 'system' && Boolean(media?.matches))
      document.documentElement.dataset.theme = dark ? 'dark' : 'light'
      document.documentElement.style.colorScheme = dark ? 'dark' : 'light'
    }
    apply()
    media?.addEventListener('change', apply)
    return () => media?.removeEventListener('change', apply)
  }, [theme])

  useEffect(() => { document.documentElement.dataset.density = density }, [density])

  const reviewer = session?.reviewer ?? reviewers.find((item) => item.identifier === reviewerId) ?? null
  const requiredCapability = route.name === 'fuentes' ? 'sources.read'
    : route.name === 'importaciones' ? 'sources.read'
    : route.name === 'seccion' && ['trabajo', 'revision/cola', 'catalogo/trabajo', 'revision/validaciones', 'catalogo/segunda'].includes(route.id) ? 'review.read'
    : route.name === 'seccion' && route.id === 'exportaciones' ? 'export.read'
    : route.name === 'seccion' && ['datos/cuarentena', 'catalogo/novedades'].includes(route.id) ? 'sources.read'
    : route.name === 'seccion' && route.id === 'revisores' ? '' : 'catalog.read'
  const allowed = !requiredCapability || may(requiredCapability)
  const active = activeNavId(route.name, route.name === 'seccion' ? route.id : null)
  const activeLabel = NAV.find((item) => item.id === active)?.label ?? (active === 'revisores' ? 'Equipo y preferencias' : 'Resumen')
  const changeReviewer = (identifier: string) => {
    setReviewerId(identifier)
    if (identifier) localStorage.setItem('farmalidacion.reviewer', identifier)
    else localStorage.removeItem('farmalidacion.reviewer')
  }

  return (
    <FilterLayoutContext.Provider value={reportFilterOpen}>
    <div className={`layout app-shell${navigationCollapsed ? ' app-shell--collapsed' : ''}`}>
      <a className='skip-link' href='#workspace-content' onClick={event => { event.preventDefault(); document.getElementById('workspace-content')?.focus() }}>Ir al contenido</a>
      <aside className='app-sidebar'>
        <div className='brand'>
          <img className='brand__mark' src='/brand-mark.svg' alt='' aria-hidden='true' />
          <span className='brand__name'>Farmalidación</span>
        </div>

        <nav aria-label='Navegación principal'>
          <ul>
            {NAV.filter(item => item.id === 'datos' ? may('sources.read') || may('export.read') : may(item.id === 'fichas' ? 'catalog.read' : 'review.read')).map((item) => (
              <li key={item.id}>
                <button
                  type='button'
                  className={`nav__item${active === item.id ? ' nav__item--active' : ''}`}
                  aria-current={active === item.id ? 'page' : undefined}
                  title={navigationCollapsed ? item.label : undefined}
                  onClick={() => navigate(item.id === 'datos' && !may('sources.read') ? '/exportaciones' : item.path)}
                >
                  <NavIcon icon={item.icon} />
                  <span>{item.label}</span>
                </button>
              </li>
            ))}
          </ul>
        </nav>
        <div className='app-sidebar__footer'>
          {may('catalog.read') && <button type='button' className={`nav__item${route.name === 'inicio' ? ' nav__item--active' : ''}`} title={navigationCollapsed ? 'Resumen' : undefined} onClick={() => navigate('/')}><Home className='nav__icon' aria-hidden='true' /><span>Resumen</span></button>}
          <button type='button' className={`nav__item${active === 'revisores' ? ' nav__item--active' : ''}`} title={navigationCollapsed ? 'Equipo y preferencias' : undefined} onClick={() => navigate('/revisores')}><Users className='nav__icon' aria-hidden='true' /><span>Equipo y preferencias</span></button>
          {may('catalog.read') && <div className='dashboard-freshness dashboard-freshness--topbar'>
            <span className='dashboard-freshness__dot' aria-hidden='true' />
            <span>
              <strong>Última importación</strong>
              <small>
                {database?.last_import_at
                  ? formatDateTime(database.last_import_at)
                  : 'Sin importaciones'}
              </small>
            </span>
          </div>}
        </div>
      </aside>

      <div className='app-shell__workspace'>
        <header className='topbar'>
          <div className='app-shell__location'>
            <button
              type='button'
              className='app-shell__toggle'
              aria-label={navigationCollapsed ? 'Expandir navegación' : 'Plegar navegación'}
              aria-expanded={!navigationCollapsed}
              disabled={filtersOpen}
              title={filtersOpen ? 'Cierra los filtros para expandir la navegación' : undefined}
              onClick={() => {
                const next = !sidebarCollapsed
                setSidebarCollapsed(next)
                localStorage.setItem('farmalidacion.sidebar.collapsed', String(next))
              }}
            >
              {navigationCollapsed ? <PanelLeftOpen size={18} aria-hidden='true' /> : <PanelLeftClose size={18} aria-hidden='true' />}
            </button>
            <span className='app-shell__breadcrumb'>Espacio de trabajo <span aria-hidden='true'>/</span> <strong>{activeLabel}</strong></span>
          </div>
          <div className='topbar__actions'>
            {database?.mode === 'demo' && <span className='mode-chip mode-chip--demo' aria-label='Base de datos de demostración'>DEMO</span>}
            <button type='button' className='account-summary' onClick={() => navigate('/revisores')} aria-label='Identidad y acceso'>
              <span className='account-summary__avatar' aria-hidden='true'>{(reviewer?.display_name ?? '?').slice(0, 1).toUpperCase()}</span>
              <span><small>{session ? 'Sesión corporativa' : reviewer ? 'Identidad del piloto' : 'Acceso'}</small><strong>{reviewer?.display_name ?? 'Sin identificar'}</strong></span>
            </button>
          </div>
        </header>

        <div className='main'>
          <main className='content' id='workspace-content' tabIndex={-1}>
            <ModeBanner info={database} />
            {!allowed ? <section className='screen'><h1>Acceso restringido</h1><p>No tienes permiso para este apartado.</p><button type='button' className='button' onClick={() => navigate('/revisores')}>Ir a mi cuenta</button></section> : <>
            {route.name === 'inicio' && <DashboardScreen />}
            {route.name === 'fichas' && (
              <RealRecordListScreen reviewer={reviewer} reviewers={reviewers} />
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
            {route.name === 'seccion' && (route.id === 'trabajo' || route.id === 'revision/cola' || route.id === 'catalogo/trabajo') && (
              <SectionWorkspace group='work' active='queue'><QueueScreen reviewer={reviewer} /></SectionWorkspace>
            )}
            {route.name === 'seccion' && (route.id === 'revision/validaciones' || route.id === 'catalogo/segunda') && (
              <SectionWorkspace group='work' active='second'><SecondReviewScreen reviewer={reviewer} /></SectionWorkspace>
            )}
            {route.name === 'seccion' && route.id === 'exportaciones' && (
              <SectionWorkspace group='data' active='exports'><ExportsScreen reviewer={reviewer} /></SectionWorkspace>
            )}
            {route.name === 'seccion' && route.id === 'catalogo/novedades' && (
              <SectionWorkspace group='work' active='changes'><MaintenanceScreen /></SectionWorkspace>
            )}
            {route.name === 'seccion' && route.id === 'revisores' && <div className='screen preferences-screen'>
              <PageHeader eyebrow='Configuración' title='Equipo y preferencias' description='Ajusta tu espacio de trabajo y consulta cómo se gestiona el acceso del equipo.' />
              <div className='preferences-screen__overview'>
                <AppearancePreferences theme={theme} density={density} onThemeChange={next => { setTheme(next); saveAppearance('theme', next) }} onDensityChange={next => { setDensity(next); saveAppearance('density', next) }} />
                {session ? <section className='panel identity-preferences'><h2>Identidad y acceso</h2><p className='muted'>Sesión corporativa verificada. Tus permisos se comprueban en cada operación.</p><div className='identity-preferences__current'><span><strong>{session.reviewer.display_name}</strong><small>{session.reviewer.role_label}</small></span><button type='button' className='button' onClick={session.logout}>Cerrar sesión</button></div></section> : <PilotIdentity reviewers={reviewers} reviewer={reviewer} onChange={changeReviewer} />}
              </div>
              {may('team.manage') && <ReviewersScreen embedded />}
              {session && !may('team.manage') && <TeamDirectory />}
              {session && may('team.manage') && <AccessAdministration />}
            </div>}
            {route.name === 'seccion' && !['trabajo', 'revision/cola', 'catalogo/trabajo', 'revision/validaciones', 'catalogo/segunda', 'catalogo/novedades', 'datos/cuarentena', 'exportaciones', 'revisores'].includes(route.id) && (
              <section className='screen'><h1>Página no encontrada</h1><p className='muted'>Este enlace no corresponde a un apartado disponible.</p><button type='button' className='button button--primary' onClick={() => navigate('/fichas')}>Volver al catálogo</button></section>
            )}
            </>}
          </main>
        </div>
      </div>
    </div>
    </FilterLayoutContext.Provider>
  )
}
