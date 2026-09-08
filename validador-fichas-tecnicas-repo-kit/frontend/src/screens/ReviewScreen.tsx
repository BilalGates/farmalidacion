import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { ApiError, fetchRecord, saveDecision } from '../api/client'
import type {
  BlockInstance,
  FieldValue,
  Reviewer,
  TargetRecord,
  ValidationState,
} from '../api/types'
import { ProvenanceList } from '../components/ProvenanceList'
import { RoadmapNote } from '../components/RoadmapNote'
import { ROADMAP_NOTES, conflictLabel, sourceLabel } from '../domain/vocabulary'
import { navigate } from '../navigation'
import { FieldRow } from './FieldRow'
import '../review-workspace.css'

/**
 * Pantalla canónica de revisión (DEV-503), servida por `/records/*`.
 *
 * Sustituye a las dos experiencias que existían por separado: la vertical DEMO
 * sobre `/records` y la ficha real de sólo lectura sobre `/insights`. Ambas
 * mostraban procedencia con código distinto, y mantener dos representaciones de
 * la trazabilidad es mantener dos sitios donde puede degradarse sin que nadie
 * lo note.
 *
 * `/insights/*` sigue siendo la superficie de consulta (listados, métricas); la
 * revisión —lectura y escritura— pasa por `/records/*`, que es donde viven las
 * barreras de `validation_states` y `reviewer_identity`.
 *
 * Tres zonas: contexto de la ficha, campo de trabajo y evidencia del campo
 * activo. La evidencia acompaña al campo en lugar de vivir en un modal porque
 * revisar consiste precisamente en comparar valor y fuente a la vez.
 */

/** Agrupa ocurrencias por tipo conservando su ordinal: nunca las fusiona. */
function groupBlocks(blocks: BlockInstance[]): [string, BlockInstance[]][] {
  const grouped = new Map<string, BlockInstance[]>()
  for (const block of blocks) {
    const list = grouped.get(block.block_type) ?? []
    list.push(block)
    grouped.set(block.block_type, list)
  }
  return [...grouped.entries()]
}

const RESOLVED_STATES: readonly ValidationState[] = [
  'confirmado',
  'corregido',
  'no_consta',
  'no_aplica',
  'descartado',
]

/** Nombre legible del registro. No se inventa si la fuente no lo trae. */
function recordTitle(record: TargetRecord): string {
  const named = record.blocks
    .flatMap((block) => block.values)
    .find((value) => ['ME_DESCRIPCION', 'DESCRIPCION', 'NOMBRE'].includes(value.field_name))
  return named?.literal_value ?? record.id
}

export function ReviewScreen({
  recordId,
  reviewer,
  backTo = '/fichas',
}: {
  recordId: string
  reviewer: Reviewer | null
  backTo?: string
}) {
  const [record, setRecord] = useState<TargetRecord | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [savingId, setSavingId] = useState<string | null>(null)
  const [activeId, setActiveId] = useState<string | null>(null)
  const fieldsRef = useRef<HTMLDivElement>(null)
  // Descarta respuestas de cargas anteriores: al cambiar de ficha deprisa, una
  // respuesta tardía sobrescribiría la ficha que el revisor ya está viendo.
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
    return () => {
      generation.current += 1
    }
  }, [load])

  const fields: FieldValue[] = useMemo(
    () => record?.blocks.flatMap((block) => block.values) ?? [],
    [record],
  )
  const activeField = fields.find((value) => value.id === activeId) ?? fields[0] ?? null

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

  if (error !== null && record === null) {
    return (
      <div className='screen'>
        <p className='alert alert--error' role='alert'>
          {error}
        </p>
        <button type='button' className='button' onClick={() => navigate(backTo)}>
          Volver al listado
        </button>
      </div>
    )
  }

  if (record === null) {
    return (
      <p className='muted' role='status'>
        Cargando ficha…
      </p>
    )
  }

  const conflicts = fields.filter((value) => value.has_conflict)
  const resolved = fields.filter((value) =>
    RESOLVED_STATES.includes(value.validation_state),
  ).length

  return (
    <div className='screen'>
      <button type='button' className='button button--ghost back' onClick={() => navigate(backTo)}>
        ← Volver al listado
      </button>

      {/* Zona A — contexto de la ficha. */}
      <div className='screen__head'>
        <div>
          <p className='eyebrow'>Revisión de ficha</p>
          <h1>{recordTitle(record)}</h1>
          <p className='lede'>
            <code>{record.id}</code> · {record.entity_type}
          </p>
        </div>
      </div>

      {record.external_identifiers.length > 0 && (
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
          </dl>
        </section>
      )}

      {conflicts.length > 0 && (
        <section className='panel'>
          <h2>Discrepancias entre fuentes</h2>
          <ul className='conflicts'>
            {conflicts.map((value) => (
              <li key={value.id}>
                <span className='conflicts__field'>{value.field_name}</span>
                <span className='badge badge--requiere_revision'>
                  {conflictLabel(value.conflict_status)}
                </span>
                {/* El valor afirmado se muestra aquí y no sólo en el campo: el
                    resumen debe bastar para ver qué discrepa sin desplegarlo. */}
                <span className='conflicts__claim'>
                  {value.provenance.map((item) => sourceLabel(item.provenance_role)).join(', ')}:{' '}
                  <strong>{value.literal_value ?? 'sin valor'}</strong>
                </span>
              </li>
            ))}
          </ul>
          <p className='note'>
            Ninguna discrepancia se resuelve automáticamente: los valores en conflicto conservan su
            procedencia y la decisión corresponde a un farmacéutico.
          </p>
          <RoadmapNote title='Resolución de discrepancias' note={ROADMAP_NOTES.discrepancias} />
        </section>
      )}

      {notice && (
        <p className='alert alert--ok' role='status'>
          {notice}
        </p>
      )}
      {error && (
        <p className='alert alert--error' role='alert'>
          {error}
        </p>
      )}

      <p role='status'>
        {resolved} de {fields.length} campos revisados
      </p>

      <div className='review-workspace'>
        {/* Zona B — campo de trabajo. */}
        <div
          ref={fieldsRef}
          aria-label='Campos del registro'
          onKeyDown={(event) => {
            if (!event.altKey || !['ArrowDown', 'ArrowUp'].includes(event.key)) return
            event.preventDefault()
            const rows = Array.from(
              fieldsRef.current?.querySelectorAll<HTMLElement>('[data-review-field]') ?? [],
            )
            const index = rows.findIndex((row) => row.dataset.reviewField === activeField?.id)
            const next = rows[index + (event.key === 'ArrowDown' ? 1 : -1)]
            next?.focus()
          }}
        >
          {groupBlocks(record.blocks).map(([blockType, blocks]) => (
            <section className='panel' key={blockType}>
              <h2>{blockType}</h2>
              {blocks.map((block) => (
                <div className='occurrence' key={block.id}>
                  <p className='occurrence__label'>Ocurrencia {block.ordinal}</p>
                  {block.values.map((value) => (
                    <div
                      key={value.id}
                      data-review-field={value.id}
                      tabIndex={0}
                      onFocus={() => setActiveId(value.id)}
                      className={activeField?.id === value.id ? 'review-field--active' : ''}
                    >
                      <FieldRow
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

        {/* Zona C — evidencia y procedencia del campo activo. */}
        <aside className='panel review-evidence' aria-label='Evidencia del campo activo'>
          <h2>Evidencia · {activeField?.field_name ?? 'Sin campos'}</h2>
          {activeField ? (
            <ProvenanceList provenance={activeField.provenance} />
          ) : (
            <p className='muted'>Este registro no tiene campos almacenados.</p>
          )}
        </aside>

        <footer className='panel review-shortcuts'>
          Alt+↓ siguiente campo · Alt+↑ anterior · Tab recorrer controles · Enter activar
        </footer>
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
