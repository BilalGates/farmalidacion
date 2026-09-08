import { useCallback, useEffect, useRef, useState } from 'react'

import { ApiError, fetchRecord, saveDecision } from '../api/client'
import type { BlockInstance, Reviewer, TargetRecord, ValidationState } from '../api/types'
import { RoadmapNote } from '../components/RoadmapNote'
import { ROADMAP_NOTES, conflictLabel, sourceLabel } from '../domain/vocabulary'
import { navigate } from '../navigation'
import { FieldRow } from './FieldRow'
import '../review-workspace.css'

/**
 * Agrupa las ocurrencias por tipo de bloque conservando su ordinal.
 *
 * No se fusionan: dos ocurrencias del mismo bloque son filas distintas del
 * modelo y colapsarlas es exactamente lo que la regla de bloques repetibles
 * prohíbe. Se agrupan solo para titularlas juntas en pantalla.
 */
function groupBlocks(blocks: BlockInstance[]): [string, BlockInstance[]][] {
  const grouped = new Map<string, BlockInstance[]>()
  for (const block of blocks) {
    const list = grouped.get(block.block_type) ?? []
    list.push(block)
    grouped.set(block.block_type, list)
  }
  return [...grouped.entries()]
}

export function RecordDetailScreen({
  recordId,
  reviewer,
}: {
  recordId: string
  reviewer: Reviewer | null
}) {
  const [record, setRecord] = useState<TargetRecord | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [savingId, setSavingId] = useState<string | null>(null)
  const [activeId, setActiveId] = useState<string | null>(null)
  const fieldsRef = useRef<HTMLDivElement>(null)
  const generation = useRef(0)

  const load = useCallback(() => {
    const current = ++generation.current
    fetchRecord(recordId)
      .then((result) => {
        if (current !== generation.current) return
        setRecord(result)
        setError(null)
      })
      .catch((cause: unknown) => {
        if (current !== generation.current) return
        setError(cause instanceof ApiError ? cause.message : 'Error inesperado.')
        setRecord(null)
      })
  }, [recordId])

  useEffect(() => {
    load()
    return () => { generation.current += 1 }
  }, [load])

  async function handleSave(
    fieldValueId: string,
    state: ValidationState,
    finalValue: string | null,
    comment: string | null,
  ) {
    if (reviewer === null) return
    setSavingId(fieldValueId)
    setNotice(null)
    try {
      await saveDecision(fieldValueId, {
        state,
        reviewer_id: reviewer.identifier,
        reviewer_role: 'farmaceutico',
        final_value: finalValue,
        comment,
      })
      setError(null)
      setNotice('Decisión guardada.')
      load()
    } catch (cause: unknown) {
      // El mensaje viene de las barreras del backend y se muestra literal.
      setError(cause instanceof ApiError ? cause.message : 'Error inesperado.')
    } finally {
      setSavingId(null)
    }
  }

  if (error && record === null) {
    return (
      <div className='screen'>
        <p className='alert alert--error'>{error}</p>
        <button type='button' className='button' onClick={() => navigate('/registros')}>
          Volver al listado
        </button>
      </div>
    )
  }

  if (record === null) return <p className='muted'>Cargando ficha…</p>

  const name =
    record.blocks
      .flatMap((block) => block.values)
      .find((value) => value.field_name === 'ME_DESCRIPCION')?.literal_value ?? record.id
  const conflicts = record.blocks
    .flatMap((block) => block.values)
    .filter((value) => value.has_conflict)
  const fields = record.blocks.flatMap((block) => block.values)
  const activeField = fields.find((value) => value.id === activeId) ?? fields[0]
  const resolved = fields.filter((value) => !['pendiente', 'revision_pendiente'].includes(value.validation_state)).length

  return (
    <div className='screen'>
      <button type='button' className='button button--ghost back' onClick={() => navigate('/registros')}>
        ← Volver al listado
      </button>

      <div className='screen__head'>
        <div>
          <p className='eyebrow'>Ficha de medicamento</p>
          <h1>{name}</h1>
        </div>
      </div>

      <section className='panel'>
        <h2>Identificación</h2>
        <dl className='pairs'>
          {record.external_identifiers.map((item) => (
            <div key={`${item.source_system}-${item.source_identifier}`}>
              <dt>{item.source_system}</dt>
              <dd className='cell--mono'>
                {item.source_identifier} · {item.source_version}
              </dd>
            </div>
          ))}
          <div>
            <dt>Tipo de registro</dt>
            <dd>{record.entity_type}</dd>
          </div>
        </dl>
      </section>

      <section className='panel'>
        <h2>Discrepancias entre fuentes</h2>
        {conflicts.length === 0 ? (
          <p className='muted'>No se han detectado discrepancias entre las fuentes cargadas.</p>
        ) : (
          <ul className='conflicts'>
            {conflicts.map((value) => (
              <li key={value.id}>
                <span className='conflicts__field'>{value.field_name}</span>
                <span className='badge badge--requiere_revision'>
                  {conflictLabel(value.conflict_status)}
                </span>
                <span className='conflicts__claim'>
                  {value.provenance.map((item) => sourceLabel(item.provenance_role)).join(', ')}:{' '}
                  <strong>{value.literal_value ?? 'sin valor'}</strong>
                </span>
              </li>
            ))}
          </ul>
        )}
        <p className='note'>
          Ninguna discrepancia se resuelve automáticamente: los valores en conflicto se conservan
          con su procedencia y la decisión corresponde a un farmacéutico.
        </p>
        <RoadmapNote title='Resolución de discrepancias' note={ROADMAP_NOTES.discrepancias} />
      </section>

      {notice && <p className='alert alert--ok'>{notice}</p>}
      {error && <p className='alert alert--error'>{error}</p>}

      <p role='status'>{resolved} de {fields.length} campos revisados</p>
      <div className='review-workspace'>
      <div ref={fieldsRef} aria-label='Campos del registro' onKeyDown={(event) => {
        if (!event.altKey || !['ArrowDown', 'ArrowUp'].includes(event.key)) return
        event.preventDefault()
        const rows = Array.from(fieldsRef.current?.querySelectorAll<HTMLElement>('[data-review-field]') ?? [])
        const index = rows.findIndex((row) => row.dataset.reviewField === activeField?.id)
        const next = rows[index + (event.key === 'ArrowDown' ? 1 : -1)]
        next?.focus()
      }}>
      {groupBlocks(record.blocks).map(([blockType, blocks]) => (
        <section className='panel' key={blockType}>
          <h2>{blockType}</h2>
          {blocks.map((block) => (
            <div className='occurrence' key={block.id}>
              <p className='occurrence__label'>Ocurrencia {block.ordinal}</p>
              {block.values.map((value) => (
                <div key={value.id} data-review-field={value.id} tabIndex={0}
                  onFocus={() => setActiveId(value.id)}
                  className={activeField?.id === value.id ? 'review-field--active' : ''}>
                <FieldRow
                  key={value.id}
                  value={value}
                  reviewer={reviewer}
                  saving={savingId === value.id}
                  onSave={(state, finalValue, comment) =>
                    void handleSave(value.id, state, finalValue, comment)
                  }
                />
                </div>
              ))}
            </div>
          ))}
        </section>
      ))}
      </div>
      <aside className='panel review-evidence' aria-label='Evidencia del campo activo'>
        <h2>Evidencia · {activeField?.field_name ?? 'Sin campos'}</h2>
        {activeField?.provenance.map((item) => <section key={item.source_fragment_id}>
          <h3>{sourceLabel(item.provenance_role)}</h3>
          <p>{item.locator} · Versión {item.document_version_id}</p>
          {item.literal_text ? <blockquote style={{ whiteSpace: 'pre-wrap' }}>{item.literal_text}</blockquote>
            : <p>Esta fuente no contiene un fragmento textual disponible.</p>}
        </section>)}
        {activeField?.provenance.length === 0 && <p>Sin procedencia declarada.</p>}
      </aside>
      <footer className='panel review-shortcuts'>Alt+↓ siguiente campo · Alt+↑ anterior · Tab recorrer controles · Enter activar botón</footer>
      </div>

      <section className='panel'>
        <h2>Validación farmacéutica</h2>
        <p className='note'>
          Cada decisión se guarda como un evento y no sustituye a la anterior: el historial de cada
          campo conserva quién decidió qué y cuándo. La firma es <strong>declarada</strong>, no
          demostrada, porque el piloto no incorpora autenticación.
        </p>
        <RoadmapNote title='Doble validación' note={ROADMAP_NOTES.dobleValidacion} />
        <RoadmapNote title='Extracción asistida' note={ROADMAP_NOTES.extraccion} />
        <RoadmapNote title='Contraste con CIMA' note={ROADMAP_NOTES.cima} />
      </section>
    </div>
  )
}
