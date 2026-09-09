import { useState } from 'react'

import { exportArtifactUrl, fetchExportExclusions, fetchExports } from '../api/client'
import type { ExportExclusionRow } from '../api/types'
import { useQuery } from '../api/useQuery'
import { AsyncBoundary } from '../components/AsyncState'
import { formatDateTime, formatNumber, shortHash } from '../domain/format'

/**
 * Exportaciones archivadas y sus exclusiones (DEV-604/605).
 *
 * Muestra siempre los dos números juntos: entregados y excluidos. Un listado
 * que sólo dijera cuántas filas salieron dejaría indistinguible una
 * exportación completa de una a la que le faltan mil fichas.
 */

const SEVERITY_LABELS: Record<string, string> = {
  bloqueante: 'Bloqueante',
  advertencia: 'Advertencia',
  no_aplicable: 'No aplicable',
}

const STATUS_LABELS: Record<string, string> = {
  completado: 'Completada',
  fallido: 'Fallida',
  bloqueado_por_contrato: 'Bloqueada por contrato',
}

function Exclusions({ runId }: { runId: string }) {
  const { data, error, loading } = useQuery(() => fetchExportExclusions(runId), [runId])

  return (
    <AsyncBoundary
      loading={loading}
      error={error}
      empty={data !== null && data.length === 0}
      emptyTitle='Sin exclusiones'
      emptyDetail='Todas las fichas del alcance se entregaron.'
    >
      {data && data.length > 0 && (
        <table className='table'>
          <thead>
            <tr>
              <th scope='col'>Ficha</th>
              <th scope='col'>Campo</th>
              <th scope='col'>Severidad</th>
              <th scope='col'>Regla</th>
              <th scope='col'>Motivo</th>
            </tr>
          </thead>
          <tbody>
            {data.map((item: ExportExclusionRow, index: number) => (
              <tr key={`${item.target_record_id}-${item.field_name ?? ''}-${index}`}>
                <th scope='row' className='cell--mono'>
                  {item.target_record_id || '—'}
                </th>
                <td>{item.field_name ?? '—'}</td>
                <td>
                  <span className={`badge badge--${item.severity}`}>
                    {SEVERITY_LABELS[item.severity] ?? item.severity}
                  </span>
                </td>
                <td className='cell--mono'>{item.rule}</td>
                <td className='muted'>{item.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </AsyncBoundary>
  )
}

export function ExportsScreen() {
  const [openRun, setOpenRun] = useState<string | null>(null)
  const { data, error, loading } = useQuery(() => fetchExports(), [])

  return (
    <div className='screen'>
      <div className='screen__head'>
        <div>
          <p className='eyebrow'>Exportación</p>
          <h1>Exportaciones</h1>
          <p className='lede'>
            Cada ejecución conserva su configuración y su hash, de modo que pueda
            repetirse y comprobarse.
          </p>
        </div>
      </div>

      <p className='note'>
        Ningún perfil está aceptado por el proveedor: D-011 sigue pendiente. Que un
        fichero se genere correctamente no significa que el destinatario lo acepte.
      </p>

      <AsyncBoundary
        loading={loading}
        error={error}
        empty={data !== null && data.length === 0}
        emptyTitle='Sin exportaciones'
        emptyDetail='Todavía no se ha ejecutado ninguna exportación.'
      >
        {data && data.length > 0 && (
          <table className='table'>
            <thead>
              <tr>
                <th scope='col'>Fecha</th>
                <th scope='col'>Perfil</th>
                <th scope='col'>Formato</th>
                <th scope='col'>Estado</th>
                <th scope='col'>Entregadas</th>
                <th scope='col'>Excluidas</th>
                <th scope='col'>Hash</th>
                <th scope='col'>Exclusiones</th>
                <th scope='col'>Artefacto</th>
              </tr>
            </thead>
            <tbody>
              {data.map((run) => (
                <tr key={run.run_id}>
                  <th scope='row'>{formatDateTime(run.created_at)}</th>
                  <td>
                    {run.profile_name}
                    <span className='muted'> · {shortHash(run.profile_version)}</span>
                  </td>
                  <td>{run.format.toUpperCase()}</td>
                  <td>
                    <span className={`badge badge--${run.status}`}>
                      {STATUS_LABELS[run.status] ?? run.status}
                    </span>
                  </td>
                  <td>{formatNumber(run.row_count)}</td>
                  <td>{formatNumber(run.excluded_count)}</td>
                  <td title={run.content_hash ?? undefined}>
                    <code>{shortHash(run.content_hash)}</code>
                  </td>
                  <td>
                    <button
                      type='button'
                      className='button button--ghost'
                      aria-expanded={openRun === run.run_id}
                      onClick={() =>
                        setOpenRun(openRun === run.run_id ? null : run.run_id)
                      }
                    >
                      {openRun === run.run_id ? 'Ocultar' : 'Ver'}
                    </button>
                  </td>
                  <td>
                    {run.content_hash ? (
                      <a className='button button--ghost' href={exportArtifactUrl(run.run_id)} download>
                        Descargar
                      </a>
                    ) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </AsyncBoundary>

      {openRun !== null && (
        <section className='panel'>
          <h2>Exclusiones de la ejecución</h2>
          <Exclusions runId={openRun} />
        </section>
      )}
    </div>
  )
}
