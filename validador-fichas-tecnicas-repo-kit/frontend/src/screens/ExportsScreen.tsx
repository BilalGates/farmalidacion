import { useState } from 'react'

import { ApiError, createExport, exportArtifactUrl, fetchExportExclusions, fetchExports } from '../api/client'
import type { ExportExclusionRow, Reviewer } from '../api/types'
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

function parseColumns(value: string) {
  return value.split('\n').map((line) => line.trim()).filter(Boolean).map((line) => {
    const separator = line.indexOf('=')
    if (separator < 1 || separator === line.length - 1) {
      throw new Error(`La columna «${line}» debe usar el formato SALIDA=CAMPO_ORIGEN.`)
    }
    return {
      name: line.slice(0, separator).trim(),
      source_field: line.slice(separator + 1).trim(),
    }
  })
}

export function ExportsScreen({ reviewer }: { reviewer: Reviewer | null }) {
  const [openRun, setOpenRun] = useState<string | null>(null)
  const [revision, setRevision] = useState(0)
  const [profileName, setProfileName] = useState('perfil-tecnico')
  const [format, setFormat] = useState<'csv' | 'txt' | 'xlsx'>('csv')
  const [columns, setColumns] = useState('DESCRIPCION=DESCRIPCION')
  const [recordIds, setRecordIds] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [submitMessage, setSubmitMessage] = useState<string | null>(null)
  const { data, error, loading } = useQuery(() => fetchExports(), [revision])

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitError(null)
    setSubmitMessage(null)
    if (!reviewer) {
      setSubmitError('Seleccione un revisor antes de firmar la exportación.')
      return
    }
    try {
      const parsedColumns = parseColumns(columns)
      if (parsedColumns.length === 0) throw new Error('Declare al menos una columna.')
      setSubmitting(true)
      const outcome = await createExport({
        actor_id: reviewer.identifier,
        profile_name: profileName.trim(),
        fmt: format,
        columns: parsedColumns,
        record_ids: recordIds.split(/[\n,]/).map((item) => item.trim()).filter(Boolean),
      })
      setSubmitMessage(
        `Ejecución creada: ${outcome.delivered_rows} entregadas y ${outcome.excluded_count} excluidas.`,
      )
      setOpenRun(outcome.run_id)
      setRevision((current) => current + 1)
    } catch (cause) {
      setSubmitError(cause instanceof ApiError || cause instanceof Error ? cause.message : 'No se ha podido crear la exportación.')
    } finally {
      setSubmitting(false)
    }
  }

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

      <section className='panel'>
        <h2>Nueva exportación técnica</h2>
        <p className='muted'>
          Declare el perfil usado en esta ejecución. Las columnas no se consideran un
          contrato aceptado y el backend excluirá cualquier ficha que no cumpla.
        </p>
        <form className='export-form' onSubmit={(event) => void submit(event)}>
          <label className='field'>
            <span className='field__label'>Nombre del perfil</span>
            <input required type='text' value={profileName} onChange={(event) => setProfileName(event.target.value)} />
          </label>
          <label className='field'>
            <span className='field__label'>Formato</span>
            <select value={format} onChange={(event) => setFormat(event.target.value as typeof format)}>
              <option value='csv'>CSV</option><option value='txt'>TXT</option><option value='xlsx'>XLSX</option>
            </select>
          </label>
          <label className='field field--wide'>
            <span className='field__label'>Columnas (una por línea)</span>
            <textarea required rows={4} value={columns} onChange={(event) => setColumns(event.target.value)} aria-describedby='export-columns-hint' />
            <span id='export-columns-hint' className='field__hint'>Formato: NOMBRE_SALIDA=CAMPO_ORIGEN. No transforma ni normaliza valores.</span>
          </label>
          <label className='field field--wide'>
            <span className='field__label'>IDs de ficha (opcional)</span>
            <textarea rows={2} value={recordIds} onChange={(event) => setRecordIds(event.target.value)} placeholder='Uno por línea o separados por comas' />
          </label>
          <button className='button button--primary' disabled={submitting || !reviewer || !profileName.trim()}>
            {submitting ? 'Generando…' : 'Generar exportación'}
          </button>
          {!reviewer && <p className='alert alert--error'>Seleccione un revisor en la cabecera para firmar la ejecución.</p>}
          {submitError && <p role='alert' className='alert alert--error'>{submitError}</p>}
          {submitMessage && <p role='status' className='alert alert--ok'>{submitMessage}</p>}
        </form>
      </section>

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
