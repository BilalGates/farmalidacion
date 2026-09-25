import { useEffect, useState } from 'react'
import { History, Pencil, Save, X } from 'lucide-react'

import { createEmptySourceValue, fetchEmptySourceColumns, fetchRecord, saveFieldMaintenance } from '../api/client'
import type { EmptySourceColumn, FieldValue, Reviewer, TargetRecord } from '../api/types'
import { formatDateTime } from '../domain/format'

interface Props {
  readonly recordId: string
  readonly reviewer: Reviewer | null
}

function currentValue(field: FieldValue): string | null {
  return field.maintained_value === undefined ? field.literal_value : field.maintained_value
}

function displayValue(value: string | null): string {
  if (value === null) return 'Vacío en el origen'
  if (value === '') return 'Cadena vacía'
  return value
}

export function SourceFieldsMaintenance({ recordId, reviewer }: Props) {
  const [record, setRecord] = useState<TargetRecord | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [saveError, setSaveError] = useState('')
  const [notice, setNotice] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [reason, setReason] = useState('')
  const [saving, setSaving] = useState(false)
  const [addingBlockId, setAddingBlockId] = useState<string | null>(null)
  const [emptyColumns, setEmptyColumns] = useState<EmptySourceColumn[]>([])
  const [newColumn, setNewColumn] = useState<number | null>(null)
  const [newValue, setNewValue] = useState('')
  const [newReason, setNewReason] = useState('')
  const [loadingColumns, setLoadingColumns] = useState(false)

  async function load() {
    setLoading(true)
    setLoadError('')
    try {
      setRecord(await fetchRecord(recordId))
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : 'No se pudieron cargar los campos fuente.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [recordId])

  function beginEdit(field: FieldValue) {
    setEditingId(field.id)
    setDraft(currentValue(field) ?? '')
    setReason('')
    setSaveError('')
    setNotice('')
  }

  function cancelEdit() {
    setEditingId(null)
    setReason('')
    setSaveError('')
  }

  async function save(field: FieldValue) {
    if (!record || !reviewer || !reason.trim()) return
    setSaving(true)
    setSaveError('')
    setNotice('')
    try {
      await saveFieldMaintenance(field.id, {
        expected_sequence: field.maintenance_sequence ?? 0,
        value: draft,
        actor_id: reviewer.identifier,
        reason: reason.trim(),
      })
      await load()
      setEditingId(null)
      setReason('')
      setNotice(`Campo «${field.field_name}» guardado en el historial de mantenimiento.`)
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : 'No se pudo guardar el campo.')
    } finally {
      setSaving(false)
    }
  }

  async function beginAdd(blockId: string) {
    setAddingBlockId(blockId)
    setEmptyColumns([])
    setNewColumn(null)
    setNewValue('')
    setNewReason('')
    setSaveError('')
    setNotice('')
    setLoadingColumns(true)
    try {
      const columns = await fetchEmptySourceColumns(recordId, blockId)
      setEmptyColumns(columns)
      setNewColumn(columns[0]?.source_column_index ?? null)
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : 'No se pudieron consultar las celdas vacías.')
      setAddingBlockId(null)
    } finally {
      setLoadingColumns(false)
    }
  }

  async function saveEmpty(blockId: string) {
    if (!reviewer || newColumn === null || !newValue.trim() || !newReason.trim()) return
    setSaving(true)
    setSaveError('')
    try {
      await createEmptySourceValue(recordId, blockId, {
        source_column_index: newColumn,
        value: newValue,
        actor_id: reviewer.identifier,
        reason: newReason.trim(),
      })
      await load()
      setAddingBlockId(null)
      setNotice('La celda vacía quedó completada con historial de mantenimiento.')
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : 'No se pudo completar la celda.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className='panel catalog-source-fields' aria-labelledby='catalog-source-fields-title'>
      <div className='panel__head'>
        <div>
          <p className='eyebrow'>Mantenimiento del libro maestro</p>
          <h2 id='catalog-source-fields-title'>Campos importados</h2>
        </div>
        {record && <span className='badge'>{record.blocks.reduce((total, block) => total + block.values.length, 0)} campos</span>}
      </div>
      <p className='catalog-source-fields__intro'>
        El literal del Excel se conserva. Aquí se corrige el valor de trabajo; cada cambio queda en un historial independiente de la revisión farmacéutica.
      </p>
      {!reviewer && <p className='alert badge--warning'>Seleccione un usuario en la barra superior para editar campos.</p>}
      {loading && <p role='status'>Cargando campos del libro…</p>}
      {!loading && loadError && <div className='alert alert--error' role='alert'>{loadError}<button type='button' className='button button--ghost' onClick={() => void load()}>Reintentar</button></div>}
      {!loading && record && record.blocks.length === 0 && <p className='muted'>Este registro no contiene campos importados.</p>}
      {notice && <p className='alert alert--ok' role='status'>{notice}</p>}
      {saveError && <p className='alert alert--error' role='alert'>{saveError}</p>}
      {!loading && record?.blocks.map((block) => (
        <section className='catalog-source-fields__block' key={block.id} aria-label={`${block.block_type}, ocurrencia ${block.ordinal}`}>
          <h3>{block.block_type} <span>· ocurrencia {block.ordinal}</span></h3>
          <dl className='catalog-source-fields__list'>
            {block.values.map((field) => {
              const value = currentValue(field)
              const isEditing = editingId === field.id
              return (
                <div className='catalog-source-field' key={field.id}>
                  <dt>
                    <strong>{field.field_name}</strong>
                    {field.source_column_index != null && <small>Columna Excel {field.source_column_index}</small>}
                  </dt>
                  <dd>
                    <div className='catalog-source-field__values'>
                      <p><span>Valor de trabajo</span><output>{isEditing ? draft : displayValue(value)}</output></p>
                      <p><span>Literal original</span><output>{displayValue(field.literal_value)}</output></p>
                    </div>
                    {isEditing ? (
                      <div className='catalog-source-field__editor'>
                        <label className='field'>
                          <span className='field__label'>Nuevo valor</span>
                          <textarea aria-label={`Nuevo valor para ${field.field_name}`} value={draft} rows={2} onChange={(event) => setDraft(event.target.value)} />
                        </label>
                        <label className='field'>
                          <span className='field__label'>Motivo</span>
                          <textarea aria-label={`Motivo para ${field.field_name}`} value={reason} rows={2} maxLength={2000} onChange={(event) => setReason(event.target.value)} />
                        </label>
                        <div className='catalog-source-field__actions'>
                          <button type='button' className='button button--primary' disabled={saving || !reviewer || !reason.trim() || draft === (value ?? '')} onClick={() => void save(field)}><Save size={16} aria-hidden='true' /> Guardar</button>
                          <button type='button' className='button button--ghost' disabled={saving} onClick={cancelEdit}><X size={16} aria-hidden='true' /> Cancelar</button>
                        </div>
                      </div>
                    ) : (
                      <div className='catalog-source-field__actions'>
                        <button type='button' className='button button--ghost' disabled={!reviewer || saving} onClick={() => beginEdit(field)}><Pencil size={16} aria-hidden='true' /> Editar campo</button>
                        {(field.maintenance_history?.length ?? 0) > 0 && <details className='catalog-source-field__history'>
                          <summary><History size={15} aria-hidden='true' /> Historial ({field.maintenance_history?.length})</summary>
                          <ol>{field.maintenance_history?.map((entry) => <li key={entry.sequence}>
                            <strong>v{entry.sequence}: {displayValue(entry.before_value)} → {displayValue(entry.after_value)}</strong>
                            <span>{entry.reason}</span>
                            <small>{entry.actor_id} · {formatDateTime(entry.recorded_at)}</small>
                          </li>)}</ol>
                        </details>}
                      </div>
                    )}
                  </dd>
                </div>
              )
            })}
          </dl>
          {addingBlockId === block.id ? (
            <div className='catalog-source-field__editor'>
              {loadingColumns ? <p role='status'>Consultando columnas de la hoja…</p> : emptyColumns.length === 0 ? <p className='muted'>No hay columnas vacías disponibles en esta fila.</p> : <>
                <label className='field'>
                  <span className='field__label'>Columna vacía</span>
                  <select aria-label={`Columna vacía de ${block.block_type}`} value={newColumn ?? ''} onChange={(event) => setNewColumn(Number(event.target.value))}>
                    {emptyColumns.map((column) => <option key={column.source_column_index} value={column.source_column_index}>{column.field_name} · columna {column.source_column_index}</option>)}
                  </select>
                </label>
                <label className='field'><span className='field__label'>Valor de trabajo</span><textarea aria-label='Valor para la celda vacía' value={newValue} rows={2} onChange={(event) => setNewValue(event.target.value)} /></label>
                <label className='field'><span className='field__label'>Motivo</span><textarea aria-label='Motivo para completar la celda' value={newReason} rows={2} maxLength={2000} onChange={(event) => setNewReason(event.target.value)} /></label>
                <p className='muted'>El Excel original seguirá vacío; el valor se guardará con procedencia y autoría.</p>
              </>}
              <div className='catalog-source-field__actions'>
                {emptyColumns.length > 0 && <button type='button' className='button button--primary' disabled={saving || !newValue.trim() || !newReason.trim()} onClick={() => void saveEmpty(block.id)}><Save size={16} aria-hidden='true' /> Guardar celda</button>}
                <button type='button' className='button button--ghost' disabled={saving} onClick={() => setAddingBlockId(null)}><X size={16} aria-hidden='true' /> Cancelar</button>
              </div>
            </div>
          ) : block.values.some((field) => field.source_column_index != null) && <button type='button' className='button button--ghost' disabled={!reviewer || saving} onClick={() => void beginAdd(block.id)}>Completar celda vacía</button>}
        </section>
      ))}
    </section>
  )
}
