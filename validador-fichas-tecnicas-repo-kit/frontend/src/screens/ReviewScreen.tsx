import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  ApiError,
  fetchBlockOccurrences,
  openTimingSession,
  reportFocusSpan,
  saveDecision,
} from '../api/client'
import { invalidateRecord, loadRecord } from '../api/recordCache'
import type {
  BlockInstance,
  BlockOccurrence,
  FieldValue,
  Reviewer,
  TargetRecord,
  ValidationState,
} from '../api/types'
import { ProvenanceList } from '../components/ProvenanceList'
import { ContextualChat } from '../components/ContextualChat'
import { RoadmapNote } from '../components/RoadmapNote'
import { ROADMAP_NOTES, conflictLabel, sourceLabel } from '../domain/vocabulary'
import { FocusTracker } from '../domain/focusTracker'
import { SHORTCUTS, isTypingTarget, resolveShortcut } from '../domain/shortcuts'
import { navigate } from '../navigation'
import { blockLabel, fieldLabel, searchText } from '../domain/fieldLabels'
import { clearDraft } from '../domain/drafts'
import { BlockEditor } from './BlockEditor'
import { SourceFieldsMaintenance } from './CatalogSourceFields'
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
  const sheetOrder: Record<string, number> = {
    specialty_general: 0,
    specialty_excipient: 1,
    medication_general: 0,
    medication_composition: 1,
    medication_indication: 2,
    medication_frequency: 3,
    medication_route: 4,
    medication_prescription: 5,
    medication_link: 6,
    active_ingredient_general: 0,
    active_ingredient_frequency: 1,
    active_ingredient_route: 2,
    active_ingredient_administration_advice: 3,
    active_ingredient_analytical_data: 4,
  }
  return [...grouped.entries()].sort(
    ([left], [right]) => (sheetOrder[left] ?? Number.MAX_SAFE_INTEGER)
      - (sheetOrder[right] ?? Number.MAX_SAFE_INTEGER),
  )
}

function excelColumnLabel(index: number): string {
  let value = index
  let label = ''
  while (value > 0) {
    value -= 1
    label = String.fromCharCode(65 + (value % 26)) + label
    value = Math.floor(value / 26)
  }
  return label
}

function duplicateFieldName(values: FieldValue[], name: string): boolean {
  return values.filter((value) => value.field_name === name).length > 1
}

const RESOLVED_STATES: readonly ValidationState[] = [
  'confirmado',
  'corregido',
  'no_consta',
  'no_aplica',
  'descartado',
]

const RECORD_TYPE_LABELS: Record<string, string> = {
  specialty: 'Especialidad · libro Especialidades',
  medication: 'Medicamento · libro Medicamentos',
  active_ingredient: 'Principio activo · libro Principios activos',
}

const BLOCK_SOURCE_LABELS: Record<string, { workbook: string; sheet: string; title: string }> = {
  specialty_general: { workbook: 'Especialidades', sheet: 'General', title: 'Datos generales' },
  specialty_excipient: { workbook: 'Especialidades', sheet: 'Excipientes', title: 'Excipientes' },
  medication_general: { workbook: 'Medicamentos', sheet: 'General', title: 'Datos generales' },
  medication_composition: { workbook: 'Medicamentos', sheet: 'Composicion', title: 'Composición' },
  medication_indication: { workbook: 'Medicamentos', sheet: 'Indicacion', title: 'Indicaciones' },
  medication_frequency: { workbook: 'Medicamentos', sheet: 'Frecuencia', title: 'Frecuencia' },
  medication_route: { workbook: 'Medicamentos', sheet: 'Via', title: 'Vías' },
  medication_prescription: { workbook: 'Medicamentos', sheet: 'Prescripcion', title: 'Prescripción' },
  medication_link: { workbook: 'Medicamentos', sheet: 'Links', title: 'Enlaces' },
  active_ingredient_general: { workbook: 'Principios activos', sheet: 'General', title: 'Datos generales' },
  active_ingredient_frequency: { workbook: 'Principios activos', sheet: 'Frecuencia', title: 'Frecuencia' },
  active_ingredient_route: { workbook: 'Principios activos', sheet: 'Via', title: 'Vías' },
  active_ingredient_administration_advice: { workbook: 'Principios activos', sheet: 'ConsejosAdministracion', title: 'Consejos de administración' },
  active_ingredient_analytical_data: { workbook: 'Principios activos', sheet: 'DatosAnaliticos', title: 'Datos analíticos' },
}

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
  compact = false,
  displayName,
  onBusyChange,
  onRecordChange,
}: {
  recordId: string
  reviewer: Reviewer | null
  backTo?: string
  compact?: boolean
  displayName?: string | null
  onBusyChange?: (busy: boolean) => void
  onRecordChange?: (record: TargetRecord) => void
}) {
  const [record, setRecord] = useState<TargetRecord | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [savingId, setSavingId] = useState<string | null>(null)
  const [errorFieldId, setErrorFieldId] = useState<string | null>(null)
  const [activeId, setActiveId] = useState<string | null>(null)
  const fieldsRef = useRef<HTMLDivElement>(null)
  const evidenceRef = useRef<HTMLElement>(null)
  const [helpOpen, setHelpOpen] = useState(false)
  const [sourceMaintenanceOpen, setSourceMaintenanceOpen] = useState(false)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [fieldSearch, setFieldSearch] = useState('')
  const [blockFilter, setBlockFilter] = useState('')
  const [onlyPending, setOnlyPending] = useState(false)
  const structureRequest = useRef(0)
  // Ocurrencias del bloque cuyo editor está abierto. Se piden bajo demanda:
  // la mayoría de las revisiones no editan la estructura del registro.
  const [editing, setEditing] = useState<string | null>(null)
  const [occurrences, setOccurrences] = useState<BlockOccurrence[]>([])
  // Descarta respuestas de cargas anteriores: al cambiar de ficha deprisa, una
  // respuesta tardía sobrescribiría la ficha que el revisor ya está viendo.
  const generation = useRef(0)
  const mounted = useRef(true)
  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false; structureRequest.current += 1; onBusyChange?.(false) }
  }, [onBusyChange])

  // Medición de tiempos (DEV-508). La sesión se abre una vez por ficha y
  // revisor; los tramos se declaran cerrados, de modo que si el navegador se
  // cierra a mitad el tramo abierto no llega en lugar de contar indefinidamente.
  const timingSession = useRef<string | null>(null)
  const tracker = useRef<FocusTracker | null>(null)
  if (tracker.current === null) {
    tracker.current = new FocusTracker((span) => {
      const id = timingSession.current
      if (id !== null) void reportFocusSpan(id, span)
    })
  }

  useEffect(() => {
    if (reviewer === null) return
    let cancelled = false
    openTimingSession(recordId, reviewer.identifier)
      .then((opened) => {
        if (!cancelled) timingSession.current = opened.id
      })
      // Sin medición se sigue revisando: es secundaria respecto al trabajo.
      .catch(() => undefined)
    const capture = tracker.current
    return () => {
      cancelled = true
      // Cerrar el tramo al abandonar la ficha: si no, el trabajo del último
      // campo se perdería entero.
      capture?.leave()
      timingSession.current = null
    }
  }, [recordId, reviewer])

  useEffect(() => {
    const capture = tracker.current
    // Una pestaña oculta es señal observable de que se dejó de trabajar.
    const onVisibility = () => {
      if (document.visibilityState === 'hidden') capture?.leave()
    }
    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('pagehide', onVisibility)
    return () => {
      document.removeEventListener('visibilitychange', onVisibility)
      window.removeEventListener('pagehide', onVisibility)
    }
  }, [])

  const load = useCallback(() => {
    const current = ++generation.current
    return loadRecord(recordId)
      .then((result) => {
        if (current !== generation.current) return
        setRecord(result)
        setError(null)
        return result
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
  useEffect(() => { if (record) onRecordChange?.(record) }, [record, onRecordChange])
  const matchesField = (value: FieldValue) =>
    (!onlyPending || !RESOLVED_STATES.includes(value.validation_state)) &&
    searchText(`${fieldLabel(value.field_name)} ${value.field_name}`).includes(searchText(fieldSearch))
  const visibleFields = compact ? (record?.blocks ?? [])
    .filter(block => !blockFilter || block.block_type === blockFilter)
    .flatMap(block => block.values).filter(matchesField) : fields
  const activeField = visibleFields.find(value => value.id === activeId) ?? visibleFields[0] ?? null

  async function handleSave(
    fieldValueId: string,
    state: ValidationState,
    finalValue: string | null,
    comment: string | null,
    advance = false,
  ) {
    if (reviewer === null || savingId !== null) return
    const visible = Array.from(fieldsRef.current?.querySelectorAll<HTMLElement>('[data-review-field]') ?? []).filter(row => !row.closest('[hidden]'))
    const nextId = visible[visible.findIndex(row => row.dataset.reviewField === fieldValueId) + 1]?.dataset.reviewField
    setSavingId(fieldValueId)
    onBusyChange?.(true)
    setErrorFieldId(null)
    setNotice(null)
    try {
      await saveDecision(fieldValueId, {
        state,
        reviewer_id: reviewer.identifier,
        reviewer_role: 'farmaceutico',
        final_value: finalValue,
        comment,
      })
      clearDraft(recordId, fieldValueId)
      invalidateRecord(recordId)
      if (!mounted.current) return
      setError(null)
      setNotice('Decisión guardada.')
      const refreshed = await load()
      if (advance && nextId && refreshed) {
        setActiveId(nextId)
        setExpandedId(nextId)
        requestAnimationFrame(() => {
          fieldsRef.current?.querySelector<HTMLElement>(`[data-review-field="${nextId}"]`)?.focus()
        })
      }
    } catch (cause: unknown) {
      if (!mounted.current) return
      // El mensaje viene de las barreras del backend y se muestra literal.
      setError(cause instanceof ApiError ? cause.message : 'Error inesperado.')
      // El borrador se conserva: un guardado rechazado no puede perder trabajo.
      setErrorFieldId(fieldValueId)
    } finally {
      if (mounted.current) { setSavingId(null); onBusyChange?.(false) }
    }
  }

  /** Mueve el foco al campo contiguo, sin guardar ni decidir nada. */
  const moveField = useCallback((direction: 1 | -1) => {
    const rows = Array.from(
      fieldsRef.current?.querySelectorAll<HTMLElement>('[data-review-field]') ?? [],
    ).filter((row) => !row.closest('[hidden]'))
    if (rows.length === 0) return
    const index = rows.findIndex((row) => row === document.activeElement?.closest('[data-review-field]'))
    // Si el foco no está en ningún campo, se entra por el primero.
    const next = index === -1 ? rows[0] : rows[index + direction]
    next?.focus()
  }, [])

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>) => {
      const action = resolveShortcut(event, isTypingTarget(event.target))
      if (action === null) return
      // Sólo se consume la pulsación que realmente se atiende: lo demás sigue
      // su camino hasta el control o el navegador.
      switch (action) {
        case 'campo_siguiente':
          event.preventDefault()
          moveField(1)
          return
        case 'campo_anterior':
          event.preventDefault()
          moveField(-1)
          return
        case 'ir_a_evidencia':
          event.preventDefault()
          evidenceRef.current?.focus()
          return
        case 'volver_al_campo': {
          event.preventDefault()
          const row = fieldsRef.current?.querySelector<HTMLElement>(
            `[data-review-field="${activeField?.id ?? ''}"]`,
          )
          row?.focus()
          return
        }
        case 'ayuda':
          event.preventDefault()
          setHelpOpen((open) => !open)
          return
        default:
          // `editar`, `guardar` y `cancelar` los atiende `FieldRow`, que es
          // quien conoce el estado del formulario del campo.
          return
      }
    },
    [activeField?.id, moveField],
  )

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
  const ContextPanel = compact ? 'details' : 'section'

  return (
    <div className={`screen review-screen${compact ? ' review-screen--compact' : ''}`}>
      {!compact && <button type='button' className='button button--ghost back' onClick={() => navigate(backTo)}>
        ← Volver al listado
      </button>}

      {/* Zona A — contexto de la ficha. */}
      <div className='screen__head'>
        <div>
          <p className='eyebrow'>Revisión de ficha</p>
          <h1>{displayName || recordTitle(record)}</h1>
          <p className='lede'>
            <code>{record.id}</code> · {RECORD_TYPE_LABELS[record.entity_type] ?? record.entity_type}
          </p>
        </div>
      </div>

      {record.external_identifiers.length > 0 && (
        <ContextPanel className='panel review-identification'>
          {compact ? <summary>Identificación y versiones ({record.external_identifiers.length})</summary> : <h2>Identificación</h2>}
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
        </ContextPanel>
      )}

      {conflicts.length > 0 && (
        <ContextPanel className='panel review-conflicts'>
          {compact ? <summary>Discrepancias entre fuentes · {conflicts.length} campos requieren revisión</summary> : <h2>Discrepancias entre fuentes</h2>}
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
        </ContextPanel>
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

      <div className='review-progress' role='status'>
        <span className='review-progress__label'>{resolved} de {fields.length} campos revisados</span>
        <div className='review-progress__track' aria-hidden='true'><span style={{ width: `${fields.length ? (resolved / fields.length) * 100 : 0}%` }} /></div>
        <strong>{fields.length ? Math.round((resolved / fields.length) * 100) : 0}%</strong>
      </div>

      <div className='review-workspace' onKeyDown={handleKeyDown}>
        {/* Zona B — campo de trabajo. */}
        <div ref={fieldsRef} aria-label='Campos del registro'>
          {compact && <div className='review-field-tools'>
            <label className='field'><span className='field__label'>Localizar campo</span>
              <input type='search' value={fieldSearch} placeholder='Nombre o código original'
                onChange={(event) => setFieldSearch(event.target.value)} />
            </label>
            <label className='field'><span className='field__label'>Bloque</span>
              <select value={blockFilter} onChange={(event) => setBlockFilter(event.target.value)}>
                <option value=''>Todos los bloques</option>
                {groupBlocks(record.blocks).map(([name]) => <option key={name} value={name}>{blockLabel(name)}</option>)}
              </select>
            </label>
            <label className='review-pending-filter'><input type='checkbox' checked={onlyPending}
              onChange={(event) => setOnlyPending(event.target.checked)} /> Solo campos pendientes</label>
          </div>}
          {compact && !record.blocks.some(block => (!blockFilter || block.block_type === blockFilter) && block.values.some(matchesField)) &&
            <p className='muted' role='status'>No hay campos que coincidan con los filtros.</p>}
          {groupBlocks(record.blocks).map(([blockType, blocks]) => (
            <section className='panel' key={blockType} hidden={compact && ((!!blockFilter && blockType !== blockFilter) || !blocks.some(block => block.values.some(matchesField)))}>
              <div className='panel__head'>
                <div>
                  <p className='eyebrow'>
                    {BLOCK_SOURCE_LABELS[blockType]
                      ? `Libro ${BLOCK_SOURCE_LABELS[blockType].workbook} · hoja ${BLOCK_SOURCE_LABELS[blockType].sheet}`
                      : 'Bloque del registro'}
                  </p>
                  <h2>{BLOCK_SOURCE_LABELS[blockType]?.title ?? blockType.replaceAll('_', ' ')}</h2>
                </div>
                <h2>{compact ? blockLabel(blockType) : blockType}</h2>
                <button
                  type='button'
                  className='button button--ghost'
                  aria-expanded={editing === blockType}
                  onClick={() => {
                    const request = ++structureRequest.current
                    if (editing === blockType) {
                      setEditing(null)
                      return
                    }
                    setEditing(blockType)
                    setOccurrences([])
                    void fetchBlockOccurrences(record.id, blockType)
                      .then(result => { if (request === structureRequest.current) setOccurrences(result) })
                      .catch((cause: unknown) => {
                        if (request !== structureRequest.current) return
                        setError(
                          cause instanceof ApiError ? cause.message : 'Error inesperado.',
                        )
                      })
                  }}
                >
                  {editing === blockType ? 'Cerrar estructura' : 'Editar estructura'}
                </button>
              </div>
              {editing === blockType && (
                <BlockEditor
                  recordId={record.id}
                  blockType={blockType}
                  occurrences={occurrences}
                  reviewer={reviewer}
                  onChange={(next) => {
                    setOccurrences(next)
                    invalidateRecord(record.id)
                    // Editar la estructura cambia qué campos existen: la ficha
                    // se recarga para no mostrar un modelo que ya no es el real.
                    load()
                  }}
                />
              )}
              {blocks.map((block) => (
                <div className='occurrence' key={block.id} hidden={compact && !block.values.some(matchesField)}>
                  <p className='occurrence__label'>Ocurrencia {block.ordinal}</p>
                  {block.values.map((value) => (
                    <div
                      key={value.id}
                      data-review-field={value.id}
                      hidden={compact && !matchesField(value)}
                      tabIndex={0}
                      onFocus={() => {
                        setActiveId(value.id)
                        tracker.current?.enter(value.field_name)
                      }}
                      className={activeField?.id === value.id ? 'review-field--active' : ''}
                    >
                      <FieldRow
                        value={value}
                        label={duplicateFieldName(block.values, value.field_name) && value.source_column_index != null
                          ? `${value.field_name} · columna ${excelColumnLabel(value.source_column_index)}`
                          : value.field_name}
                        recordId={record.id}
                        reviewer={reviewer}
                        saving={savingId !== null}
                        saveError={errorFieldId === value.id}
                        expanded={compact ? expandedId === value.id : undefined}
                        onExpandedChange={compact ? (open) => {
                          if (open) {
                            setExpandedId(value.id); setActiveId(value.id)
                            requestAnimationFrame(() => fieldsRef.current?.querySelector<HTMLElement>(`[data-review-field="${value.id}"]`)?.scrollIntoView?.({ block: 'start', inline: 'nearest' }))
                          }
                          else setExpandedId(current => current === value.id ? null : current)
                        } : undefined}
                        onSave={(state, finalValue, comment) =>
                          void handleSave(value.id, state, finalValue, comment)
                        }
                        onSaveAndAdvance={compact ? (state, finalValue, comment) =>
                          void handleSave(value.id, state, finalValue, comment, true) : undefined}
                      />
                    </div>
                  ))}
                </div>
              ))}
            </section>
          ))}
        </div>

        {/* Zona C — evidencia y procedencia del campo activo. */}
        <aside
          ref={evidenceRef}
          tabIndex={-1}
          className='panel review-evidence'
          aria-label='Evidencia del campo activo'
        >
          <div className='evidence-head'><span className='evidence-head__icon' aria-hidden='true'>⌕</span><div><p className='eyebrow'>Fuente activa</p><h2>Evidencia · {activeField?.field_name ?? 'Sin campos'}</h2></div></div>
          {activeField ? (
            <ProvenanceList key={activeField.id} provenance={activeField.provenance} highlightField={activeField.field_name} contextual={compact} />
          ) : (
            <p className='muted'>{fields.length ? 'No hay campos visibles con estos filtros.' : 'Este registro no tiene campos almacenados.'}</p>
          )}
          <ContextualChat recordId={recordId} />
        </aside>

        {!compact && <footer className='panel review-shortcuts'>
          <button
            type='button'
            className='button button--ghost'
            aria-expanded={helpOpen}
            onClick={() => setHelpOpen((open) => !open)}
          >
            Atajos de teclado (Shift + ?)
          </button>
          {helpOpen && (
            <dl className='shortcuts'>
              {SHORTCUTS.map((shortcut) => (
                <div key={shortcut.action}>
                  <dt>
                    <kbd>{shortcut.label}</kbd>
                  </dt>
                  <dd>{shortcut.description}</dd>
                </div>
              ))}
            </dl>
          )}
        </footer>}
      </div>

      <section className='panel'>
        <details
          className='disclosure review-source-maintenance'
          onToggle={(event) => setSourceMaintenanceOpen(event.currentTarget.open)}
          aria-label='Mantenimiento independiente de campos fuente'
        >
          <summary>Mantenimiento del libro original · editar datos importados</summary>
          <p className='note'>Corrige el dato de trabajo sin registrar una decisión farmacéutica ni alterar el literal importado. Disponible también para registros que aún no tienen identidad canónica.</p>
          {sourceMaintenanceOpen && <SourceFieldsMaintenance recordId={record.id} reviewer={reviewer} />}
        </details>
      </section>

      <section className='panel'>
        <h2>Validación farmacéutica</h2>
      {!compact && <ContextPanel className='panel review-assurance'>
        {compact ? <summary>Validación farmacéutica y trazabilidad</summary> : <h2>Validación farmacéutica</h2>}
        <p className='note'>
          Cada decisión se guarda como un evento y no sustituye a la anterior: el historial de cada
          campo conserva quién decidió qué y cuándo. La firma es <strong>declarada</strong>, no
          demostrada, porque el piloto no incorpora autenticación.
        </p>
        <RoadmapNote title='Doble validación' note={ROADMAP_NOTES.dobleValidacion} />
        <RoadmapNote title='Extracción asistida' note={ROADMAP_NOTES.extraccion} />
        <RoadmapNote title='Contraste con CIMA' note={ROADMAP_NOTES.cima} />
      </ContextPanel>}
    </div>
  )
}
