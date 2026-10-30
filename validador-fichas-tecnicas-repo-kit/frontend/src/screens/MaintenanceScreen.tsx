import { useEffect, useState } from 'react'
import { Search } from 'lucide-react'

import {
  fetchMaintenanceChange,
  fetchMaintenanceChangeHistory,
  fetchMaintenanceRuns,
  runCimaMaintenance,
} from '../api/client'
import type { MaintenanceChangeSummary } from '../api/client'
import { useQuery } from '../api/useQuery'
import { useCapability } from '../auth/SessionContext'
import { AsyncBoundary } from '../components/AsyncState'
import { PageHeader } from '../components/PageHeader'
import { FilterBar } from '../components/FilterBar'
import { formatDateTime, shortHash } from '../domain/format'

const CHANGE_LABELS: Record<number, string> = {
  1: 'Alta',
  2: 'Baja',
  3: 'Modificación',
}

const AREA_LABELS: Record<string, string> = {
  estado: 'Estado de autorización',
  comerc: 'Comercialización',
  prosp: 'Prospecto',
  ft: 'Ficha técnica',
  psum: 'Suministro',
  notasSeguridad: 'Notas de seguridad',
  matinf: 'Materiales informativos',
  otros: 'Otros',
}

function areaLabel(area: string): string {
  return AREA_LABELS[area] ?? `${area} (código nuevo de CIMA)`
}

function daysBehind(requestedDate: string): number {
  const [day, month, year] = requestedDate.split('/').map(Number)
  const lastDay = Date.UTC(year, month - 1, day)
  const now = new Date()
  const yesterday = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() - 1)
  return Math.max(0, Math.round((yesterday - lastDay) / 86_400_000))
}

function ChangeDetail({ eventId }: { eventId: string }) {
  const { data, error, loading } = useQuery(() => fetchMaintenanceChange(eventId), [eventId])

  return (
    <AsyncBoundary
      loading={loading}
      error={error}
      empty={false}
      emptyTitle='Sin detalle'
      emptyDetail='La novedad no contiene información adicional.'
    >
      {data && (
        <section className='panel' aria-label='Detalle de la novedad'>
          <div className='panel__head'>
            <h2>Diff documental</h2>
            <code title={data.source_sha256}>{shortHash(data.source_sha256)}</code>
          </div>
          {data.diff === null ? (
            <p className='state state--empty'>
              {data.areas.includes('ft') && data.new_version_id === null
                ? 'CIMA comunicó un cambio de ficha técnica, pero no ofrece sus secciones para este medicamento. Se conserva el aviso; no se ha creado una versión documental ni se han modificado campos.'
                : 'CIMA no comunica un cambio en la ficha técnica. Se conserva el aviso, sin proponer cambios en los campos maestros.'}
              {' '}Áreas notificadas: {data.areas.map(areaLabel).join(', ') || 'sin área declarada'}.
            </p>
          ) : (
            <div className='table-wrap' role='region' aria-label='Cambios documentales; desplazamiento horizontal disponible' tabIndex={0}><table className='table'>
              <thead>
                <tr>
                  <th scope='col'>Apartado</th>
                  <th scope='col'>Cambio</th>
                  <th scope='col'>Detalle</th>
                </tr>
              </thead>
              <tbody>
                {data.diff.changes.map((change) => (
                  <tr key={`${change.role}-${change.ordinal}`}>
                    <th scope='row'>{change.new_locator ?? change.old_locator ?? change.role}</th>
                    <td>{change.change_type}</td>
                    <td>
                      {change.text_diff ? <pre className='maintenance-diff'>{change.text_diff}</pre> : change.diff_kind}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table></div>
          )}
        </section>
      )}
    </AsyncBoundary>
  )
}

function ChangeCard({ item, expanded, onToggle }: {
  item: MaintenanceChangeSummary
  expanded: boolean
  onToggle: () => void
}) {
  const targets = item.catalog_targets ?? []
  const visibleTargets = targets.slice(0, 2)
  const otherTargets = targets.slice(2)
  const targetLink = (target: MaintenanceChangeSummary['catalog_targets'][number]) => (
    <li key={`${target.identity_id}-${target.national_code}`}>
      <a href={`#/catalogo/${encodeURIComponent(target.identity_id)}`}>
        <span>{target.display_name}</span>
        <small>CN {target.national_code}</small>
      </a>
    </li>
  )

  return (
    <article className='cima-change-card' aria-label={`Novedad del registro ${item.nregistro}`}>
      <div className='cima-change-card__main'>
        <div className='cima-change-card__heading'>
          <div>
            <p className='cima-change-card__date'>Registrada el {formatDateTime(item.recorded_at)}</p>
            <h3>N.º registro <span>{item.nregistro}</span></h3>
          </div>
          <span className={`cima-change-card__type cima-change-card__type--${item.change_type}`}>
            {CHANGE_LABELS[item.change_type] ?? `Tipo ${item.change_type}`}
          </span>
        </div>
        <div className='cima-change-card__areas' aria-label='Áreas notificadas'>
          {item.areas.length > 0
            ? item.areas.map((area) => <span key={area}>{areaLabel(area)}</span>)
            : <span>Sin área declarada</span>}
        </div>
        <div className='cima-change-card__targets'>
          <p>{targets.length === 1 ? 'Registro del catálogo relacionado' : `${targets.length} registros del catálogo relacionados`}</p>
          {targets.length > 0 ? (
            <>
              <ul>{visibleTargets.map(targetLink)}</ul>
              {otherTargets.length > 0 && (
                <details>
                  <summary>Mostrar {otherTargets.length} {otherTargets.length === 1 ? 'registro más' : 'registros más'}</summary>
                  <ul>{otherTargets.map(targetLink)}</ul>
                </details>
              )}
            </>
          ) : <p className='cima-change-card__empty'>Sin coincidencia exacta</p>}
        </div>
      </div>
      <div className='cima-change-card__side'>
        <div className='cima-change-card__reopened'>
          <strong>{item.affected_field_count}</strong>
          <span>{item.affected_field_count === 1 ? 'campo reabierto' : 'campos reabiertos'}</span>
        </div>
        <button type='button' className='button button--secondary' aria-expanded={expanded} onClick={onToggle}>
          {expanded ? 'Ocultar detalle' : 'Ver detalle'}
        </button>
      </div>
      {expanded && <div className='cima-change-card__detail'><ChangeDetail eventId={item.id} /></div>}
    </article>
  )
}

function HistoryPager({ page, total, pageSize, loading, onPageChange, id }: {
  page: number
  total: number
  pageSize: number
  loading: boolean
  onPageChange: (page: number) => void
  id: string
}) {
  const pageCount = Math.ceil(total / pageSize)
  if (pageCount <= 1) return null

  return (
    <nav className='maintenance-history-pager' aria-label='Páginas del histórico CIMA'>
      <button type='button' className='button button--ghost' disabled={page <= 1 || loading} onClick={() => onPageChange(page - 1)}>Más recientes</button>
      <span>Página {page} de {pageCount}</span>
      <button type='button' className='button button--ghost' disabled={page >= pageCount || loading} onClick={() => onPageChange(page + 1)}>Más antiguas</button>
      <form onSubmit={(event) => {
        event.preventDefault()
        const input = event.currentTarget.elements.namedItem(id) as HTMLInputElement
        const destination = Number(input.value)
        if (Number.isInteger(destination) && destination >= 1 && destination <= pageCount) onPageChange(destination)
      }}>
        <label htmlFor={id}>Ir a la página</label>
        <input key={page} id={id} name={id} type='number' min={1} max={pageCount} defaultValue={page} />
        <button type='submit' className='button button--secondary' disabled={loading}>Ir</button>
      </form>
    </nav>
  )
}

export function MaintenanceScreen() {
  const canRunMaintenance = useCapability('sources.manage')
  const [selected, setSelected] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [registrationInput, setRegistrationInput] = useState('')
  const [registrationFilter, setRegistrationFilter] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)
  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)
  const [runMessage, setRunMessage] = useState<string | null>(null)
  useEffect(() => {
    const interval = window.setInterval(() => setRefreshKey((value) => value + 1), 60_000)
    return () => window.clearInterval(interval)
  }, [])
  const { data, error, loading } = useQuery(
    () => fetchMaintenanceChangeHistory(page, registrationFilter),
    [page, registrationFilter, refreshKey],
  )
  const { data: runs, error: runsError } = useQuery(() => fetchMaintenanceRuns(), [refreshKey])
  const latestRun = runs?.[0]
  const latestCompleted = runs?.find((run) => run.status === 'completed')
  const delayedDays = latestCompleted ? daysBehind(latestCompleted.requested_date) : null
  const completedWithWarning = latestRun?.status === 'completed' && Boolean(latestRun.error_detail)
  const syncTone = latestRun?.status === 'completed' && (completedWithWarning || (delayedDays !== null && delayedDays > 0))
    ? 'warning' : latestRun?.status ?? 'unknown'
  const syncLabel = latestRun?.status === 'failed'
    ? 'Requiere atención'
    : latestRun?.status === 'running'
      ? 'Actualizando'
      : delayedDays !== null && delayedDays > 0
        ? 'Pendiente de actualización'
        : completedWithWarning ? 'Completada con avisos'
          : latestRun?.status === 'completed' ? 'Sincronización al día' : 'Sin consultas'

  function goToPage(nextPage: number) {
    setPage(nextPage)
    setSelected(null)
  }

  async function checkYesterday() {
    setRunning(true)
    setRunError(null)
    setRunMessage(null)
    try {
      const result = await runCimaMaintenance()
      setRunMessage(
        `Consulta de ${result.requested_date} completada: ${result.event_count} novedades del catálogo.`,
      )
      setRefreshKey((value) => value + 1)
    } catch (cause) {
      setRunError(cause instanceof Error ? cause.message : 'No se pudo consultar CIMA.')
      setRefreshKey((value) => value + 1)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className='screen cima-screen'>
      <PageHeader eyebrow='Mantenimiento continuo' title='Novedades CIMA' description='Cambios regulatorios observados y campos que requieren nueva revisión.' />
      {latestRun?.status === 'failed' && (
        <div className='state state--error' role='alert'>
          <p className='state__title'>La última consulta CIMA falló</p>
          <p className='state__detail'>
            {latestRun.requested_date} · intento {latestRun.attempt}: {latestRun.error_detail}
          </p>
        </div>
      )}
      {latestRun?.status === 'completed' && latestRun.error_detail && (
        <div className='state state--error' role='alert'>
          <p className='state__title'>La consulta CIMA terminó con documentos no disponibles</p>
          <p className='state__detail'>{latestRun.error_detail}</p>
        </div>
      )}
      {runsError && <div className='state state--error' role='alert'>No se pudo comprobar la actualización automática: {runsError}</div>}
      {latestRun?.status === 'running' && (
        <div className='state' role='status'>
          Consulta CIMA en curso desde el {latestRun.requested_date}: {latestRun.event_count} novedades nuevas procesadas en este intento.
          {delayedDays !== null && delayedDays > 0 && ` Se están recuperando ${delayedDays} días pendientes.`}
        </div>
      )}
      {runs && latestRun?.status !== 'failed' && latestRun?.status !== 'running' && (delayedDays === null || delayedDays > 0) && (
        <div className='state state--warning' role='alert'>
          {delayedDays === null
            ? 'Todavía no hay una consulta automática CIMA completada.'
            : `La consulta automática CIMA lleva ${delayedDays} ${delayedDays === 1 ? 'día' : 'días'} de retraso.`}
        </div>
      )}
      <section className='panel cima-sync' aria-label='Estado de sincronización CIMA'>
        <div className='cima-sync__top'>
          <div>
            <p className='eyebrow'>Consulta automática</p>
            <h2>Estado de sincronización</h2>
            <span className={`cima-sync__status cima-sync__status--${syncTone}`}>
              <span aria-hidden='true' />{syncLabel}
            </span>
          </div>
          {canRunMaintenance && (
            <button type='button' className='button button--primary' onClick={checkYesterday} disabled={running}>
              {running ? 'Consultando CIMA…' : 'Consultar ayer'}
            </button>
          )}
        </div>
        <dl className='cima-sync__facts'>
          <div><dt>Último día consultado</dt><dd>{latestRun?.requested_date ?? 'Sin consultas'}</dd></div>
          <div><dt>Resultado</dt><dd>{latestRun ? `${latestRun.status === 'completed' ? 'Completada' : latestRun.status === 'running' ? 'En curso' : 'Fallida'} · ${latestRun.event_count.toLocaleString('es-ES')} novedades` : 'Pendiente'}</dd></div>
        </dl>
        <p className='cima-sync__note'>Se consulta cada día cerrado. Solo se registran avisos cuyo CN coincide de forma exacta y única con el catálogo. Las correcciones requieren revisión humana.</p>
        {runMessage && <p role='status'>{runMessage}</p>}
        {runError && <p className='state__detail' role='alert'>{runError}</p>}
        {runs && runs.length > 0 && (
          <details className='cima-sync__runs'>
            <summary>Historial de consultas ({runs.length} intentos recientes)</summary>
            <ol>
              {runs.map((run) => (
                <li key={run.id}>
                  <strong>{run.requested_date}</strong><span>Intento {run.attempt} · {run.status === 'completed' ? 'completada' : run.status === 'running' ? 'en curso' : 'fallida'}</span><span>{run.event_count.toLocaleString('es-ES')} novedades</span>
                </li>
              ))}
            </ol>
          </details>
        )}
      </section>
      <section className='panel maintenance-history-search' aria-label='Buscar en el histórico CIMA'>
        <div className='maintenance-history-search__head'>
          <div>
            <p className='eyebrow'>Archivo de cambios</p>
            <h2>Histórico de novedades</h2>
            <p>Consulta los avisos conservados y abre el detalle documental cuando lo necesites.</p>
          </div>
          {data && <strong className='maintenance-history-search__total'>{data.total.toLocaleString('es-ES')} <span>novedades</span></strong>}
        </div>
        <FilterBar label='Buscar en el histórico CIMA' activeCount={registrationFilter ? 1 : 0}
          onClear={() => { setRegistrationInput(''); setRegistrationFilter(''); goToPage(1) }}
          search={
            <form role='search' onSubmit={(event) => {
              event.preventDefault()
              setRegistrationFilter(registrationInput.trim())
              goToPage(1)
            }}>
              <label className='field' htmlFor='maintenance-registration'>
                <span className='field__label'>N.º registro CIMA</span>
                <span className='input-with-icon'><Search aria-hidden='true' /><input id='maintenance-registration' type='search' value={registrationInput}
                  onChange={(event) => setRegistrationInput(event.target.value)} maxLength={80}
                  placeholder='Buscar por número de registro' /></span>
              </label>
              <button type='submit' className='button button--primary button--icon' aria-label='Buscar' title='Buscar'><Search size={16} aria-hidden='true' /></button>
            </form>
          }>
          {registrationFilter && <span className='filter-pill' data-active='true'><span className='filter-pill__label'>Registro</span><strong>{registrationFilter}</strong></span>}
        </FilterBar>
        {data && (
          <p className='state__detail'>
            {data.total > 0
              ? `Mostrando ${((page - 1) * data.page_size + 1).toLocaleString('es-ES')}–${Math.min(page * data.page_size, data.total).toLocaleString('es-ES')} de ${data.total.toLocaleString('es-ES')} novedades conservadas${registrationFilter ? ` para el registro ${registrationFilter}` : ''}.`
              : 'No hay novedades que mostrar.'}
          </p>
        )}
      </section>
      {data && <HistoryPager page={page} total={data.total} pageSize={data.page_size} loading={loading} onPageChange={goToPage} id='history-page-top' />}
      <AsyncBoundary
        loading={loading}
        error={error}
        empty={data !== null && data.items.length === 0}
        emptyTitle='Sin novedades'
        emptyDetail={registrationFilter ? 'No hay novedades para ese número de registro.' : 'No se han registrado cambios CIMA que coincidan de forma exacta con el catálogo.'}
      >
        {data && data.items.length > 0 && (
          <div className='cima-change-list' aria-label='Novedades CIMA'>
            {data.items.map((item) => <ChangeCard key={item.id} item={item}
              expanded={selected === item.id}
              onToggle={() => setSelected(selected === item.id ? null : item.id)} />)}
          </div>
        )}
      </AsyncBoundary>
      {data && <HistoryPager page={page} total={data.total} pageSize={data.page_size} loading={loading} onPageChange={goToPage} id='history-page-bottom' />}
    </div>
  )
}
