import { useState } from 'react'

import {
  fetchMaintenanceChange,
  fetchMaintenanceChanges,
  fetchMaintenanceRuns,
} from '../api/client'
import { useQuery } from '../api/useQuery'
import { AsyncBoundary } from '../components/AsyncState'
import { formatDateTime, shortHash } from '../domain/format'

const CHANGE_LABELS: Record<number, string> = {
  1: 'Alta',
  2: 'Baja',
  3: 'Modificación',
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
            <p className='state state--empty'>Este cambio no incluye una nueva versión de ficha.</p>
          ) : (
            <table className='table'>
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
            </table>
          )}
        </section>
      )}
    </AsyncBoundary>
  )
}

export function MaintenanceScreen() {
  const [selected, setSelected] = useState<string | null>(null)
  const { data, error, loading } = useQuery(() => fetchMaintenanceChanges(), [])
  const { data: runs } = useQuery(() => fetchMaintenanceRuns(), [])
  const latestRun = runs?.[0]

  return (
    <div className='screen'>
      <div className='screen__head'>
        <div>
          <p className='eyebrow'>Mantenimiento continuo</p>
          <h1>Novedades CIMA</h1>
          <p className='lede'>Cambios regulatorios observados y campos que requieren nueva revisión.</p>
        </div>
      </div>
      {latestRun?.status === 'failed' && (
        <div className='state state--error' role='alert'>
          <p className='state__title'>La última consulta CIMA falló</p>
          <p className='state__detail'>
            {latestRun.requested_date} · intento {latestRun.attempt}: {latestRun.error_detail}
          </p>
        </div>
      )}
      <AsyncBoundary
        loading={loading}
        error={error}
        empty={data !== null && data.length === 0}
        emptyTitle='Sin novedades'
        emptyDetail='No se han registrado cambios CIMA.'
      >
        {data && data.length > 0 && (
          <table className='table'>
            <thead>
              <tr>
                <th scope='col'>Registrada</th>
                <th scope='col'>N.º registro</th>
                <th scope='col'>Tipo</th>
                <th scope='col'>Áreas</th>
                <th scope='col'>Campos reabiertos</th>
                <th scope='col'>Detalle</th>
              </tr>
            </thead>
            <tbody>
              {data.map((item) => (
                <tr key={item.id}>
                  <th scope='row'>{formatDateTime(item.recorded_at)}</th>
                  <td className='cell--mono'>{item.nregistro}</td>
                  <td>{CHANGE_LABELS[item.change_type] ?? `Tipo ${item.change_type}`}</td>
                  <td>{item.areas.join(', ') || 'Sin área declarada'}</td>
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
              ))}
            </tbody>
          </table>
        )}
      </AsyncBoundary>
      {selected && <ChangeDetail eventId={selected} />}
    </div>
  )
}
