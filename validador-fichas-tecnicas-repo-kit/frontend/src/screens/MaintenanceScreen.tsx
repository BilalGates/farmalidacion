import { Fragment, useEffect, useState } from 'react'

import {
  fetchMaintenanceChange,
  fetchMaintenanceChangeHistory,
  fetchMaintenanceRuns,
  runCimaMaintenance,
} from '../api/client'
import { useQuery } from '../api/useQuery'
import { useCapability } from '../auth/SessionContext'
import { AsyncBoundary } from '../components/AsyncState'
import { PageHeader } from '../components/PageHeader'
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
    <div className='screen'>
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
        <div className='state state--error' role='alert'>
          {delayedDays === null
            ? 'Todavía no hay una consulta automática CIMA completada.'
            : `La consulta automática CIMA lleva ${delayedDays} ${delayedDays === 1 ? 'día' : 'días'} de retraso.`}
        </div>
      )}
      <section className='panel' aria-label='Estado de sincronización CIMA'>
        <div className='panel__head'>
          <h2>Estado de sincronización</h2>
          {canRunMaintenance && (
            <button type='button' className='button button--primary' onClick={checkYesterday} disabled={running}>
              {running ? 'Consultando CIMA…' : 'Consultar ayer'}
            </button>
          )}
        </div>
        <p>
          {latestRun
            ? `Último día consultado: ${latestRun.requested_date} · ${latestRun.status === 'completed' ? 'completada' : latestRun.status === 'running' ? 'en curso' : 'fallida'} · ${latestRun.event_count} novedades.`
            : 'Todavía no hay consultas registradas.'}
        </p>
        <p className='state__detail'>
          Se consulta cada día cerrado. Solo se registran avisos cuyo CN coincide de forma exacta y única con el catálogo.
          Las correcciones siguen requiriendo revisión humana.
        </p>
        {runMessage && <p role='status'>{runMessage}</p>}
        {runError && <p className='state__detail' role='alert'>{runError}</p>}
        {runs && runs.length > 0 && (
          <details>
            <summary>Historial de consultas ({runs.length} intentos recientes)</summary>
            <ol>
              {runs.map((run) => (
                <li key={run.id}>
                  {run.requested_date} · intento {run.attempt} · {run.status === 'completed' ? 'completada' : run.status === 'running' ? 'en curso' : 'fallida'} · {run.event_count} novedades
                </li>
              ))}
            </ol>
          </details>
        )}
      </section>
      <section className='panel maintenance-history-search' aria-label='Buscar en el histórico CIMA'>
        <div className='panel__head'><h2>Histórico de novedades</h2></div>
        <form onSubmit={(event) => {
          event.preventDefault()
          setRegistrationFilter(registrationInput.trim())
          setPage(1)
          setSelected(null)
        }}>
          <label htmlFor='maintenance-registration'>N.º registro CIMA</label>{' '}
          <input
            id='maintenance-registration'
            type='search'
            value={registrationInput}
            onChange={(event) => setRegistrationInput(event.target.value)}
            maxLength={80}
            placeholder='Todos los registros'
          />{' '}
          <button type='submit' className='button button--secondary'>Buscar</button>
        </form>
        {data && (
          <p className='state__detail'>
            {data.total.toLocaleString('es-ES')} novedades conservadas{registrationFilter && ` para el registro ${registrationFilter}`}.
          </p>
        )}
      </section>
      <AsyncBoundary
        loading={loading}
        error={error}
        empty={data !== null && data.items.length === 0}
        emptyTitle='Sin novedades'
        emptyDetail={registrationFilter ? 'No hay novedades para ese número de registro.' : 'No se han registrado cambios CIMA que coincidan de forma exacta con el catálogo.'}
      >
        {data && data.items.length > 0 && (
          <div className='table-wrap' role='region' aria-label='Novedades CIMA; desplazamiento horizontal disponible' tabIndex={0}><table className='table'>
            <thead>
              <tr>
                <th scope='col'>Registrada</th>
                <th scope='col'>N.º registro</th>
                <th scope='col'>Tipo</th>
                <th scope='col'>Áreas</th>
                <th scope='col'>Registros del catálogo</th>
                <th scope='col' className='cell--num'>Campos reabiertos</th>
                <th scope='col'>Detalle</th>
              </tr>
            </thead>
            <tbody>
                {data.items.map((item) => (
                <Fragment key={item.id}>
                <tr>
                  <th scope='row'>{formatDateTime(item.recorded_at)}</th>
                  <td className='cell--mono'>{item.nregistro}</td>
                  <td>{CHANGE_LABELS[item.change_type] ?? `Tipo ${item.change_type}`}</td>
                  <td>{item.areas.map(areaLabel).join(', ') || 'Sin área declarada'}</td>
                  <td>
                    {item.catalog_targets?.length ? item.catalog_targets.map((target) => (
                      <p key={`${target.identity_id}-${target.national_code}`}>
                        <a href={`#/catalogo/${encodeURIComponent(target.identity_id)}`}>
                          {target.display_name} · CN {target.national_code}
                        </a>
                      </p>
                    )) : 'Sin coincidencia exacta'}
                  </td>
                  <td className='cell--num'>{item.affected_field_count}</td>
                  <td>
                    <button
                      type='button'
                      className='button button--ghost'
                      aria-expanded={selected === item.id}
                      onClick={() => setSelected(selected === item.id ? null : item.id)}
                    >
                      {selected === item.id ? 'Ocultar' : 'Ver'}
                    </button>
                  </td>
                </tr>
                {selected === item.id && (
                  <tr className='maintenance-detail-row'>
                    <td colSpan={7}>
                      <ChangeDetail eventId={item.id} />
                    </td>
                  </tr>
                )}
                </Fragment>
              ))}
            </tbody>
          </table></div>
        )}
      </AsyncBoundary>
      {data && data.total > data.page_size && (
        <nav className='maintenance-history-pager' aria-label='Páginas del histórico CIMA'>
          <button type='button' className='button button--ghost' disabled={page <= 1 || loading} onClick={() => { setPage(page - 1); setSelected(null) }}>Más recientes</button>
          <span>Página {page} de {Math.ceil(data.total / data.page_size)}</span>
          <button type='button' className='button button--ghost' disabled={page >= Math.ceil(data.total / data.page_size) || loading} onClick={() => { setPage(page + 1); setSelected(null) }}>Más antiguas</button>
          <form onSubmit={(event) => {
            event.preventDefault()
            const input = event.currentTarget.elements.namedItem('history-page') as HTMLInputElement
            const destination = Number(input.value)
            if (Number.isInteger(destination) && destination >= 1 && destination <= Math.ceil(data.total / data.page_size)) {
              setPage(destination)
              setSelected(null)
            }
          }}>
            <label htmlFor='history-page'>Ir a la página</label>{' '}
            <input key={page} id='history-page' name='history-page' type='number' min={1} max={Math.ceil(data.total / data.page_size)} defaultValue={page} />{' '}
            <button type='submit' className='button button--secondary' disabled={loading}>Ir</button>
          </form>
        </nav>
      )}
    </div>
  )
}
