import { useEffect, useState } from 'react'

import { fetchNomenclatorComparison, saveNomenclatorDecision } from '../api/client'
import type { NomenclatorComparison, NomenclatorComparisonField, Reviewer } from '../api/types'
import { useCapability } from '../auth/SessionContext'
import { formatDateTime } from '../domain/format'

const STATUS: Record<NomenclatorComparisonField['status'], string> = {
  coincide: 'Coincide',
  difiere: 'Diferencia por revisar',
  complemento: 'Dato complementario',
  sin_comparacion: 'Sin valor maestro comparable',
}

interface Props {
  readonly identityId: string
  readonly reviewer: Reviewer | null
}

export function NomenclatorComparisonPanel({ identityId, reviewer }: Props) {
  const canDecide = useCapability('review.write')
  const [comparison, setComparison] = useState<NomenclatorComparison | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [reasons, setReasons] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState<string | null>(null)

  async function reload() {
    setLoading(true)
    setError('')
    try {
      setComparison(await fetchNomenclatorComparison(identityId))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo consultar Nomenclátor.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void reload() }, [identityId])

  async function decide(field: NomenclatorComparisonField, action: 'aceptar' | 'descartar' | 'pendiente') {
    if (!comparison?.snapshot_sha256 || !reviewer || !reasons[field.field_name]?.trim()) return
    setSaving(field.field_name)
    setError('')
    setNotice('')
    try {
      await saveNomenclatorDecision(identityId, {
        field_name: field.field_name,
        snapshot_sha256: comparison.snapshot_sha256,
        expected_sequence: field.decision_history.at(-1)?.sequence ?? 0,
        action,
        actor_id: reviewer.identifier,
        reason: reasons[field.field_name].trim(),
      })
      setReasons((current) => ({ ...current, [field.field_name]: '' }))
      setComparison(await fetchNomenclatorComparison(identityId))
      setNotice('Decisión añadida al historial de Nomenclátor.')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo guardar la decisión.')
    } finally {
      setSaving(null)
    }
  }

  return <section className='panel nomenclator-comparison' aria-labelledby='nomenclator-comparison-title'>
    <div className='panel__head'><div><p className='eyebrow'>Fuente estructurada</p><h2 id='nomenclator-comparison-title'>Nomenclátor</h2></div></div>
    <p className='muted'>Comparación por código nacional exacto. Aceptar registra un dato complementario con autor y motivo; el valor del maestro no se sustituye automáticamente.</p>
    {loading && <p role='status'>Consultando instantánea de Nomenclátor…</p>}
    {error && <p className='alert alert--error' role='alert'>{error}</p>}
    {notice && <p className='alert alert--ok' role='status'>{notice}</p>}
    {!loading && !error && comparison && !comparison.available && <p className='note'>Aún no hay una instantánea Nomenclátor configurada para esta vista.</p>}
    {!loading && comparison?.available && !comparison.source_row_id && <p className='note'>No hay una fila Nomenclátor con este código nacional exacto.</p>}
    {!loading && comparison?.source_row_id && <>
      <p className='nomenclator-comparison__source'>CN {comparison.code} · fila {comparison.source_line} · identificador de origen {comparison.source_row_id} · actualización más reciente {comparison.latest_source_date ?? 'sin fecha'} · SHA-256 {comparison.snapshot_sha256}</p>
      <div className='nomenclator-comparison__items'>{comparison.fields.map((field) => <article className='nomenclator-comparison__item' key={field.field_name}>
        <div className='nomenclator-comparison__item-head'><h3>{field.label}</h3><span className={`badge ${field.status === 'difiere' ? 'badge--warning' : ''}`}>{STATUS[field.status]}</span></div>
        <dl className='definition'><div><dt>Nomenclátor</dt><dd>{field.source_value}</dd></div><div><dt>Maestro {field.master_field ? `(${field.master_field})` : ''}</dt><dd>{field.master_value ?? 'Sin campo equivalente confirmado'}</dd></div><div><dt>Nivel</dt><dd>{field.level}</dd></div></dl>
        {field.latest_decision && <p className='note'>Última decisión: {field.latest_decision.action} · {field.latest_decision.actor_id} · {formatDateTime(field.latest_decision.recorded_at)}. {field.latest_decision.reason}</p>}
        {field.decision_history.length > 0 && <details><summary>Historial ({field.decision_history.length})</summary><ol>{field.decision_history.map((entry) => <li key={entry.sequence}>{entry.action} · {entry.actor_id} · {formatDateTime(entry.recorded_at)} · {entry.reason}</li>)}</ol></details>}
        {field.status !== 'coincide' && canDecide && reviewer && <div className='nomenclator-comparison__decision'>
          <label className='field'><span>Motivo de la decisión</span><textarea value={reasons[field.field_name] ?? ''} onChange={(event) => setReasons((current) => ({ ...current, [field.field_name]: event.target.value }))} rows={2} maxLength={2000} /></label>
          <div className='catalog-source-field__actions'>
            {reviewer.role === 'farmaceutico' && <button type='button' className='button button--primary' disabled={saving !== null || !reasons[field.field_name]?.trim()} onClick={() => void decide(field, 'aceptar')}>Aceptar como complemento</button>}
            <button type='button' className='button button--secondary' disabled={saving !== null || !reasons[field.field_name]?.trim()} onClick={() => void decide(field, 'descartar')}>Descartar</button>
            <button type='button' className='button button--ghost' disabled={saving !== null || !reasons[field.field_name]?.trim()} onClick={() => void decide(field, 'pendiente')}>Dejar pendiente</button>
          </div>
        </div>}
      </article>)}</div>
    </>}
  </section>
}
