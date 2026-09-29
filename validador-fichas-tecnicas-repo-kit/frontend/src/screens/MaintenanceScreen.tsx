import { Fragment, useState } from 'react'

import {
  fetchMaintenanceChange,
  fetchMaintenanceChanges,
  fetchMaintenanceRuns,
  runCimaMaintenance,
} from '../api/client'
import { useQuery } from '../api/useQuery'
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
              CIMA no comunica un cambio en la ficha técnica. Se conserva el aviso, sin proponer cambios en los campos maestros.
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
  const [selected, setSelected] = useState<string | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)
  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)
  const [runMessage, setRunMessage] = useState<string | null>(null)
  const { data, error, loading } = useQuery(() => fetchMaintenanceChanges(), [refreshKey])
  const { data: runs } = useQuery(() => fetchMaintenanceRuns(), [refreshKey])
  const latestRun = runs?.[0]

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
      <section className='panel' aria-label='Estado de sincronización CIMA'>
        <div className='panel__head'>
          <h2>Estado de sincronización</h2>
          <button type='button' className='button button--primary' onClick={checkYesterday} disabled={running}>
            {running ? 'Consultando CIMA…' : 'Consultar ayer'}
          </button>
        </div>
        <p>
          {latestRun
            ? `Último día consultado: ${latestRun.requested_date} · ${latestRun.status === 'completed' ? 'completada' : latestRun.status} · ${latestRun.event_count} novedades.`
            : 'Todavía no hay consultas registradas.'}
        </p>
        <p className='state__detail'>
          Se consulta el último día cerrado. Solo se registran avisos cuyo CN coincide de forma exacta y única con el catálogo.
          Las correcciones siguen requiriendo revisión humana.
        </p>
        {runMessage && <p role='status'>{runMessage}</p>}
        {runError && <p className='state__detail' role='alert'>{runError}</p>}
      </section>
      <AsyncBoundary
        loading={loading}
        error={error}
        empty={data !== null && data.length === 0}
        emptyTitle='Sin novedades'
        emptyDetail='No se han registrado cambios CIMA.'
      >
        {data && data.length > 0 && (
          <div className='table-wrap' role='region' aria-label='Novedades CIMA; desplazamiento horizontal disponible' tabIndex={0}><table className='table'>
            <thead>
              <tr>
                <th scope='col'>Registrada</th>
                <th scope='col'>N.º registro</th>
                <th scope='col'>Tipo</th>
                <th scope='col'>Áreas</th>
                <th scope='col'>Registros del catálogo</th>
                <th scope='col'>Campos reabiertos</th>
                <th scope='col'>Detalle</th>
              </tr>
            </thead>
            <tbody>
                {data.map((item) => (
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
                  <td>{item.affected_field_count}</td>
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
    </div>
  )
}
