import { useEffect, useState } from 'react'
import { AlertTriangle, ChevronLeft, ChevronRight, Pencil, Save, X } from 'lucide-react'

import {
  ApiError,
  fetchQuarantinedRows,
  saveQuarantinedFieldMaintenance,
} from '../api/client'
import type { QuarantinedField, QuarantinedSourceRow, Reviewer } from '../api/types'
import { formatDateTime } from '../domain/format'

const PAGE_SIZE = 50
const WORKBOOKS: Record<string, string> = {
  'Especialidades-CargaMaster190626.xlsx': 'Especialidades',
  'Medicamento-cargaMaster25062026.xlsx': 'Medicamentos',
  'PrincipioActivoCargaMaster-22062026.xlsx': 'Principios activos',
}

function valueLabel(value: string | null): string {
  if (value === null) return 'Vacío en el origen'
  if (value === '') return 'Cadena vacía'
  return value
}

export function QuarantinedRecordsScreen({ reviewer }: { reviewer: Reviewer | null }) {
  const [rows, setRows] = useState<QuarantinedSourceRow[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [workbook, setWorkbook] = useState('')
  const [selectedId, setSelectedId] = useState('')
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [saveError, setSaveError] = useState('')
  const [notice, setNotice] = useState('')
  const [editingColumn, setEditingColumn] = useState<number | null>(null)
  const [draft, setDraft] = useState('')
  const [reason, setReason] = useState('')
  const [saving, setSaving] = useState(false)
  const selected = rows.find((row) => row.id === selectedId) ?? rows[0] ?? null

  async function load(nextOffset = offset, nextWorkbook = workbook, preferredId = selectedId) {
    setLoading(true)
    setLoadError('')
    try {
      const page = await fetchQuarantinedRows({
        sourceWorkbook: nextWorkbook || undefined,
        limit: PAGE_SIZE,
        offset: nextOffset,
      })
      setRows(page.items)
      setTotal(page.total)
      setOffset(nextOffset)
      setWorkbook(nextWorkbook)
      setSelectedId(page.items.some((row) => row.id === preferredId)
        ? preferredId
        : page.items[0]?.id ?? '')
    } catch (error) {
      setLoadError(error instanceof ApiError ? error.message : 'No se pudieron cargar las filas.')
    } finally {
      setLoading(false)
    }
  }

  // Carga sólo al entrar; los cambios de página/filtro llaman load desde sus controles.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void load(0, '', '') }, [])

  function beginEdit(field: QuarantinedField) {
    setEditingColumn(field.source_column_index)
    setDraft(field.maintained_value ?? '')
    setReason('')
    setSaveError('')
    setNotice('')
  }

  async function save(field: QuarantinedField) {
    if (!selected || !reviewer || !reason.trim()) return
    setSaving(true)
    setSaveError('')
    setNotice('')
    try {
      await saveQuarantinedFieldMaintenance(selected.id, field.source_column_index, {
        expected_sequence: field.maintenance_sequence,
        value: draft,
        actor_id: reviewer.identifier,
        reason: reason.trim(),
      })
      await load(offset, workbook, selected.id)
      setEditingColumn(null)
      setNotice(`Campo «${field.field_name}» guardado. La fila conserva su estado en cuarentena.`)
    } catch (error) {
      setSaveError(error instanceof ApiError ? error.message : 'No se pudo guardar el campo.')
    } finally {
      setSaving(false)
    }
  }

  const pageNumber = Math.floor(offset / PAGE_SIZE) + 1
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className='screen quarantine-screen'>
      <div className='screen__head'>
        <div>
          <p className='eyebrow'>Datos preservados, relación pendiente</p>
          <h1>Filas en cuarentena</h1>
          <p className='lede'>Corrige celdas fuente sin asignar un padre ni cambiar por qué la fila quedó apartada.</p>
        </div>
        <span className='badge badge--warning'><AlertTriangle size={15} aria-hidden='true' /> {total} filas</span>
      </div>

      <section className='panel'>
        <div className='panel__head'>
          <div><p className='eyebrow'>Revisión de importación</p><h2>Origen y motivo</h2></div>
          <label className='field quarantine-screen__filter'>
            <span className='field__label'>Libro</span>
            <select value={workbook} onChange={(event) => void load(0, event.target.value, '')}>
              <option value=''>Todos los libros</option>
              {Object.entries(WORKBOOKS).map(([filename, label]) => <option key={filename} value={filename}>{label}</option>)}
            </select>
          </label>
        </div>
        {!reviewer && <p className='alert badge--warning'>Seleccione un usuario arriba para mantener campos.</p>}
        {loadError && <p className='alert alert--error' role='alert'>{loadError}<button className='button button--ghost' type='button' onClick={() => void load()}>Reintentar</button></p>}
        {loading && <p role='status'>Cargando filas…</p>}
        {!loading && !loadError && rows.length === 0 && <p className='muted'>No hay filas en cuarentena para este filtro.</p>}

        {!loading && rows.length > 0 && (
          <div className='quarantine-screen__layout'>
            <div className='table-scroll'>
              <table className='data-table quarantine-screen__table'>
                <thead><tr><th>Libro</th><th>Hoja · fila</th><th>Motivo</th></tr></thead>
                <tbody>{rows.map((row) => (
                  <tr key={row.id} className={row.id === selected?.id ? 'quarantine-screen__selected' : ''}>
                    <td><button type='button' className='quarantine-screen__row-button' onClick={() => { setSelectedId(row.id); setEditingColumn(null); setSaveError(''); setNotice('') }}>{WORKBOOKS[row.source_workbook] ?? row.source_workbook}</button></td>
                    <td><button type='button' className='quarantine-screen__row-button cell--mono' onClick={() => setSelectedId(row.id)}>{row.source_locator}</button></td>
                    <td><span className='badge badge--warning'>{row.reason_code}</span></td>
                  </tr>
                ))}</tbody>
              </table>
              <div className='pagination quarantine-screen__pagination'>
                <span>Mostrando {offset + 1}–{Math.min(offset + rows.length, total)} de {total} · página {pageNumber} de {pageCount}</span>
                <div>
                  <button type='button' className='button button--ghost' aria-label='Página anterior' disabled={offset === 0 || loading} onClick={() => void load(Math.max(0, offset - PAGE_SIZE))}><ChevronLeft size={16} aria-hidden='true' /> Anterior</button>
                  <button type='button' className='button button--ghost' aria-label='Página siguiente' disabled={offset + PAGE_SIZE >= total || loading} onClick={() => void load(offset + PAGE_SIZE)}><ChevronRight size={16} aria-hidden='true' /> Siguiente</button>
                </div>
              </div>
            </div>

            {selected && (
              <section className='quarantine-detail' aria-label='Detalle de fila en cuarentena'>
                <p className='eyebrow'>{WORKBOOKS[selected.source_workbook] ?? selected.source_workbook} · {selected.source_locator}</p>
                <h2>{selected.reason_code}</h2>
                <p>{selected.reason}</p>
                <p className='note'>Los cambios de abajo actualizan únicamente el valor de trabajo. La fila no se vincula automáticamente y seguirá apareciendo aquí hasta resolver el motivo.</p>
                {notice && <p className='alert alert--ok' role='status'>{notice}</p>}
                {saveError && <p className='alert alert--error' role='alert'>{saveError}</p>}
                <dl className='quarantine-fields'>{selected.fields.map((field) => {
                  const editing = editingColumn === field.source_column_index
                  return (
                    <div className='quarantine-field' key={field.source_column_index}>
                      <dt><strong>{field.field_name}</strong><small>Columna Excel {field.source_column_index}</small></dt>
                      <dd>
                        <p><span>Valor de trabajo</span><output>{editing ? draft : valueLabel(field.maintained_value)}</output></p>
                        <p><span>Literal original</span><output>{valueLabel(field.literal_value)}</output></p>
                        {editing ? (
                          <div className='quarantine-field__editor'>
                            <label className='field'><span className='field__label'>Nuevo valor</span><textarea aria-label={`Nuevo valor para ${field.field_name}`} rows={2} value={draft} onChange={(event) => setDraft(event.target.value)} /></label>
                            <label className='field'><span className='field__label'>Motivo</span><textarea aria-label={`Motivo para ${field.field_name}`} rows={2} value={reason} maxLength={2000} onChange={(event) => setReason(event.target.value)} /></label>
                            <div className='catalog-source-field__actions'>
                              <button type='button' className='button button--primary' disabled={saving || !reviewer || !reason.trim() || draft === (field.maintained_value ?? '')} onClick={() => void save(field)}><Save size={16} aria-hidden='true' /> Guardar</button>
                              <button type='button' className='button button--ghost' disabled={saving} onClick={() => setEditingColumn(null)}><X size={16} aria-hidden='true' /> Cancelar</button>
                            </div>
                          </div>
                        ) : (
                          <div className='catalog-source-field__actions'>
                            <button type='button' className='button button--ghost' disabled={!reviewer || saving} onClick={() => beginEdit(field)}><Pencil size={16} aria-hidden='true' /> Editar campo</button>
                            {field.maintenance_history.length > 0 && <details className='catalog-source-field__history'><summary>Historial ({field.maintenance_history.length})</summary><ol>{field.maintenance_history.map((entry) => <li key={entry.sequence}><strong>v{entry.sequence}: {valueLabel(entry.before_value)} → {valueLabel(entry.after_value)}</strong><span>{entry.reason}</span><small>{entry.actor_id} · {formatDateTime(entry.recorded_at)}</small></li>)}</ol></details>}
                          </div>
                        )}
                      </dd>
                    </div>
                  )
                })}</dl>
              </section>
            )}
          </div>
        )}
      </section>
    </div>
  )
}
