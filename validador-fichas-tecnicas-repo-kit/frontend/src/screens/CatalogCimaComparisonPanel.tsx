import { useEffect, useState } from 'react'

import { fetchCatalogCimaComparison, saveCatalogCimaDecision } from '../api/client'
import type {
  CatalogCimaComparison,
  CatalogCimaDocument,
  CatalogCimaDecisionWrite,
  TargetRecord,
} from '../api/types'

interface Props {
  readonly identityId: string
  readonly reviewerId: string
  readonly documents: CatalogCimaDocument[]
  readonly record: TargetRecord
  readonly onRefreshRecord: () => Promise<void>
}

const STATUS_LABELS: Record<CatalogCimaComparison['status'], string> = {
  coincide: 'Coincidencia literal',
  difiere: 'Diferencia literal',
  falta_registro: 'Falta valor en el maestro',
  falta_cima: 'Falta ficha/apartado CIMA',
  no_comparable: 'No comparable',
  requiere_criterio: 'Requiere criterio farmacéutico',
}

function comparisonKey(item: CatalogCimaComparison): string {
  return `${item.field_value_id}:${item.document_version_id ?? 'sin-cima'}`
}

export function CatalogCimaComparisonPanel({
  identityId,
  reviewerId,
  documents,
  record,
  onRefreshRecord,
}: Props) {
  const [items, setItems] = useState<CatalogCimaComparison[]>([])
  const [selectedKey, setSelectedKey] = useState('')
  const [sectionLocator, setSectionLocator] = useState('')
  const [reason, setReason] = useState('')
  const [correctedValue, setCorrectedValue] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  async function reload() {
    setLoading(true)
    setError('')
    try {
      const result = await fetchCatalogCimaComparison(identityId)
      setItems(result)
      setSelectedKey((current) => result.some((item) => comparisonKey(item) === current)
        ? current
        : result.length
          ? comparisonKey(result.find((item) =>
            item.catalog_field_id && item.status !== 'no_comparable') ?? result[0])
          : '')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo comparar con CIMA.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void reload() }, [identityId])

  const selected = items.find((item) => comparisonKey(item) === selectedKey)
  const sourceField = selected && record.blocks
    .flatMap((block) => block.values)
    .find((field) => field.id === selected.field_value_id)
  const document = selected?.document_version_id
    ? documents.find((item) => item.document_version_id === selected.document_version_id)
    : undefined
  const canDecide = Boolean(
    reviewerId && selected?.catalog_field_id && selected.document_version_id &&
    selected.section_locators.length && sectionLocator && selected.status !== 'no_comparable',
  )

  async function decide(action: CatalogCimaDecisionWrite['action']) {
    if (!selected?.document_version_id || !canDecide) return
    if (!reason.trim()) {
      setError('Indique el motivo de la decisión.')
      return
    }
    setSaving(true)
    setError('')
    setNotice('')
    const payload: CatalogCimaDecisionWrite = {
      document_version_id: selected.document_version_id,
      section_locator: sectionLocator,
      action,
      expected_maintenance_sequence: sourceField?.maintenance_sequence ?? 0,
      actor_id: reviewerId,
      reason: reason.trim(),
    }
    if (action === 'corregir') payload.corrected_value = correctedValue
    try {
      await saveCatalogCimaDecision(identityId, selected.field_value_id, payload)
      if (action === 'corregir') await onRefreshRecord()
      await reload()
      setReason('')
      setCorrectedValue('')
      setSectionLocator('')
      setNotice('La decisión quedó registrada con su versión y apartado CIMA.')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo guardar la decisión.')
    } finally {
      setSaving(false)
    }
  }

  return <section className='panel catalog-cima-comparison' aria-labelledby='catalog-cima-comparison-title'>
    <div className='panel__head'>
      <div><p className='eyebrow'>Revisión humana</p><h3 id='catalog-cima-comparison-title'>Comparación campo a campo</h3></div>
      <button className='button button--ghost' type='button' onClick={() => void reload()} disabled={loading}>Actualizar comparación</button>
    </div>
    <p className='muted'>La comparación es literal y usa los apartados declarados en el catálogo de campos. Una coincidencia o diferencia textual no resuelve por sí sola la equivalencia clínica. Los campos parciales o interpretables requieren criterio farmacéutico.</p>
    {loading ? <p role='status'>Comparando campos…</p> : error && items.length === 0 ? <p role='alert'>{error}</p> : items.length === 0 ?
      <p>No hay campos fuente para comparar en este registro.</p> : <>
        <label className='field'>
          <span className='field__label'>Campo del maestro</span>
          <select value={selectedKey} onChange={(event) => {
            setSelectedKey(event.target.value)
            setSectionLocator('')
            setError('')
            setNotice('')
          }}>
            {items.map((item) => <option key={comparisonKey(item)} value={comparisonKey(item)}>
              {item.block_type} · ocurrencia {item.occurrence} · {item.field_name}
              {item.source_column_index == null ? '' : ` · columna ${item.source_column_index}`} — {STATUS_LABELS[item.status]}
              {item.document_name ? ` · CIMA ${item.document_name}` : ''}
            </option>)}
          </select>
        </label>
        {selected && <div className='catalog-cima-comparison__detail'>
          <p><strong>Resultado:</strong> {STATUS_LABELS[selected.status]}</p>
          <p>{selected.reason}</p>
          <p><strong>Valor de trabajo:</strong> {selected.master_value === null || selected.master_value === '' ? 'Sin valor' : <code>{selected.master_value}</code>}</p>
          {selected.catalog_classification && <p className='muted'>Clasificación del catálogo: {selected.catalog_classification}</p>}
          {selected.document_version_id && <p className='muted'>Versión CIMA: {selected.source_version || selected.document_version_id} · SHA-256: <code>{selected.content_hash}</code></p>}
          {selected.section_locators.length > 0 ? <>
            <p><strong>Apartados candidatos:</strong> {selected.section_locators.map((locator) => {
              const index = document?.sections.findIndex((section) => section.locator === locator) ?? -1
              const href = index >= 0 && selected.document_version_id
                ? `#cima-${selected.document_version_id}-${index}`
                : undefined
              return href
                ? <a className='catalog-cima-comparison__section-link' key={locator} href={href}>Apartado {locator}</a>
                : <span className='catalog-cima-comparison__section-link' key={locator}>Apartado {locator}</span>
            })}</p>
            {selected.document_version_id && selected.catalog_field_id && selected.status !== 'no_comparable' && <div className='catalog-cima-comparison__actions'>
              <label className='field'>
                <span className='field__label'>Apartado que sustenta la decisión</span>
                <select value={sectionLocator} onChange={(event) => setSectionLocator(event.target.value)}>
                  <option value=''>Seleccione un apartado</option>
                  {selected.section_locators.map((locator) => <option key={locator} value={locator}>Apartado {locator}</option>)}
                </select>
              </label>
              <label className='field'>
                <span className='field__label'>Motivo</span>
                <textarea value={reason} onChange={(event) => setReason(event.target.value)} rows={2} />
              </label>
              <label className='field'>
                <span className='field__label'>Valor de trabajo corregido</span>
                <input value={correctedValue} onChange={(event) => setCorrectedValue(event.target.value)} />
              </label>
              <div className='catalog-cima-comparison__buttons'>
                <button className='button button--primary' type='button' disabled={!canDecide || saving || !correctedValue.trim()} onClick={() => void decide('corregir')}>Guardar corrección</button>
                <button className='button button--ghost' type='button' disabled={!canDecide || saving} onClick={() => void decide('revisado')}>Registrar revisión</button>
                <button className='button button--ghost' type='button' disabled={!canDecide || saving} onClick={() => void decide('descartar')}>Descartar comparación</button>
                <button className='button button--ghost' type='button' disabled={!canDecide || saving} onClick={() => void decide('pendiente')}>Dejar pendiente</button>
              </div>
              {!reviewerId && <p className='muted'>Seleccione un revisor en la cabecera para registrar decisiones.</p>}
            </div>}
          </> : <p className='muted'>No hay un apartado candidato que se pueda abrir para este campo.</p>}
          {selected.decision_history.length > 0 && <div className='catalog-cima-comparison__history'>
            <h4>Decisiones anteriores</h4>
            <ol>{selected.decision_history.map((decision) => <li key={`${decision.sequence}-${decision.document_version_id}`}>
              {decision.action} · {decision.actor_id} · apartado {decision.section_locator} · {decision.reason}
            </li>)}</ol>
          </div>}
        </div>}
      </>}
    {error && items.length > 0 && <p role='alert'>{error}</p>}
    {notice && <p role='status'>{notice}</p>}
  </section>
}
