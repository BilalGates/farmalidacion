import { useEffect, useState } from 'react'
import { Archive, ExternalLink, GitBranch, History, Save } from 'lucide-react'

import {
  fetchCatalogHistory,
  fetchCatalogIdentity,
  fetchCatalogClassifications,
  fetchCatalogRelations,
  setCatalogClassification,
  updateCatalogIdentity,
} from '../api/client'
import type { CatalogClassification, CatalogIdentity, CatalogRelation, CatalogRevision, Reviewer } from '../api/types'
import { AsyncBoundary } from '../components/AsyncState'
import { formatDateTime, orDash } from '../domain/format'
import { navigate } from '../navigation'
import { SourceFieldsMaintenance } from './CatalogSourceFields'

const TYPE_LABELS: Record<string, string> = {
  commercial_product: 'Producto comercial', authorization: 'Autorización',
  presentation: 'Presentación', dcpf: 'DCPF', dcp: 'DCP', dcsa: 'DCSA',
  active_ingredient: 'Sustancia activa',
}
const SOURCE_WORKBOOK_LABELS: Record<string, string> = {
  especialidades: 'Especialidades-CargaMaster190626.xlsx',
  medicamentos: 'Medicamento-cargaMaster25062026.xlsx',
  principios_activos: 'PrincipioActivoCargaMaster-22062026.xlsx',
}

const RELATION_LABELS: Record<string, string> = {
  product_authorization: 'Producto → autorización',
  authorization_presentation: 'Autorización → presentación',
  presentation_dcpf: 'Presentación → DCPF',
  dcpf_dcp: 'DCPF → DCP',
  dcp_dcsa: 'DCP → DCSA',
  dcp_active_ingredient: 'Composición',
}

const COMMERCIAL_CLASSES = [
  ['original', 'Original'], ['generico', 'Genérico'],
  ['biosimilar', 'Biosimilar'], ['sin_clasificar', 'Sin clasificar'],
] as const
const CONDITIONS = [
  ['huerfano', 'Huérfano'], ['estupefaciente', 'Estupefaciente'],
  ['psicotropico', 'Psicotrópico'],
  ['especial_control_medico', 'Especial control médico'],
  ['uso_hospitalario', 'Uso hospitalario'],
] as const

interface Props {
  readonly identityId: string
  readonly reviewer: Reviewer | null
}

export function CatalogIdentityScreen({ identityId, reviewer }: Props) {
  const [identity, setIdentity] = useState<CatalogIdentity | null>(null)
  const [history, setHistory] = useState<CatalogRevision[]>([])
  const [relations, setRelations] = useState<CatalogRelation[]>([])
  const [classifications, setClassifications] = useState<CatalogClassification[]>([])
  const [name, setName] = useState('')
  const [code, setCode] = useState('')
  const [reason, setReason] = useState('')
  const [error, setError] = useState<Error | null>(null)
  const [saveError, setSaveError] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [notice, setNotice] = useState('')

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const record = await fetchCatalogIdentity(identityId)
      const [revisions, linked, labels] = await Promise.all([
        fetchCatalogHistory(identityId), fetchCatalogRelations(identityId),
        record.identity_type === 'presentation' ? fetchCatalogClassifications(identityId) : Promise.resolve([]),
      ])
      setIdentity(record)
      setName(record.display_name)
      setCode(record.code ?? '')
      setHistory(revisions)
      setRelations(linked)
      setClassifications(labels)
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('No se pudo abrir el expediente.'))
    } finally { setLoading(false) }
  }

  useEffect(() => { void load() }, [identityId])

  async function save(active: boolean) {
    if (!identity || !reviewer || !reason.trim() || !name.trim()) return
    setSaving(true)
    setNotice('')
    setSaveError('')
    try {
      const updated = await updateCatalogIdentity(identity.id, {
        expected_version: identity.version,
        display_name: name.trim(), code: code.trim() || null, active,
        actor_id: reviewer.identifier, reason: reason.trim(),
      })
      setIdentity(updated)
      setReason('')
      setNotice(active ? 'Cambios guardados en el historial.' : 'Registro archivado sin borrar su historia.')
      setHistory(await fetchCatalogHistory(identity.id))
    } catch (caught) {
      setSaveError(caught instanceof Error ? caught.message : 'No se pudieron guardar los cambios.')
    } finally { setSaving(false) }
  }

  async function changeClassification(type: 'commercial_class' | 'condition', value: string, active: boolean) {
    if (!identity || !reviewer) return
    const explanation = window.prompt(
      active ? 'Motivo para añadir esta clasificación:' : 'Motivo para retirar esta clasificación:',
    )
    if (!explanation?.trim()) return
    setSaveError('')
    setNotice('')
    try {
      await setCatalogClassification(identity.id, {
        classification_type: type, value, active,
        actor_id: reviewer.identifier, reason: explanation.trim(),
      })
      setClassifications(await fetchCatalogClassifications(identity.id))
      setHistory(await fetchCatalogHistory(identity.id))
      setNotice('Clasificación actualizada y añadida al historial.')
    } catch (caught) {
      setSaveError(caught instanceof Error ? caught.message : 'No se pudo actualizar la clasificación.')
    }
  }

  return (
    <div className='screen catalog-record'>
      <button type='button' className='button button--ghost back' onClick={() => navigate('/fichas')}>
        ← Volver al catálogo
      </button>
      <AsyncBoundary loading={loading} error={error?.message ?? null} empty={!identity} emptyTitle='Expediente no disponible' emptyDetail='La identidad solicitada no existe o ya no está accesible.' onRetry={() => void load()}>
        {identity && <>
          <header className='catalog-record__head'>
            <div>
              <p className='eyebrow'>{TYPE_LABELS[identity.identity_type] ?? identity.identity_type}</p>
              <h1>{identity.display_name}</h1>
              <p className='lede'>Código <strong>{orDash(identity.code)}</strong> · versión editable {identity.version}</p>
            </div>
            <span className={`badge ${identity.active ? 'badge--validado' : 'badge--descartado'}`}>
              {identity.active ? 'Vigente' : 'Archivado'}
            </span>
          </header>

          {notice && <p className='alert alert--ok' role='status'>{notice}</p>}
          {saveError && <p className='alert alert--error' role='alert'>{saveError}</p>}
          {!reviewer && <p className='alert badge--warning'>Seleccione un revisor en la barra superior para guardar cambios.</p>}

          <div className='catalog-record__grid'>
            <section className='panel catalog-editor' aria-labelledby='catalog-data-title'>
              <div className='panel__head'><div><p className='eyebrow'>Estado canónico</p><h2 id='catalog-data-title'>Datos editables</h2></div></div>
              <div className='catalog-form'>
                <label className='field'><span className='field__label'>Nombre visible</span><input type='text' value={name} onChange={(event) => setName(event.target.value)} /></label>
                <label className='field'><span className='field__label'>Código</span><input type='text' value={code} onChange={(event) => setCode(event.target.value)} /></label>
                <label className='field catalog-form__reason'><span className='field__label'>Motivo del cambio</span><textarea value={reason} onChange={(event) => setReason(event.target.value)} placeholder='Explique qué se corrige y por qué' rows={3} /></label>
              </div>
              <div className='catalog-actions'>
                <button className='button button--primary' type='button' disabled={saving || !reviewer || !reason.trim() || !name.trim()} onClick={() => void save(true)}><Save size={16} aria-hidden='true' /> Guardar cambios</button>
                {identity.active && <button className='button button--danger' type='button' disabled={saving || !reviewer || !reason.trim()} onClick={() => void save(false)}><Archive size={16} aria-hidden='true' /> Archivar</button>}
              </div>
            </section>

            <aside className='catalog-record__side'>
              <section className='panel'><p className='eyebrow'>Procedencia</p><h2>Valor fuente</h2><dl className='definition'>{identity.source_workbook && <div><dt>Libro Excel</dt><dd>{SOURCE_WORKBOOK_LABELS[identity.source_workbook] ?? identity.source_workbook}</dd></div>}<div><dt>Sistema</dt><dd>{identity.source_system}</dd></div><div><dt>Versión</dt><dd>{identity.source_version}</dd></div><div><dt>Literal conservado</dt><dd><code>{orDash(identity.source_literal)}</code></dd></div></dl>{identity.target_record_id && <button type='button' className='button' onClick={() => navigate(`/registros/${encodeURIComponent(identity.target_record_id!)}`)}><ExternalLink size={16} aria-hidden='true' /> Ver datos importados</button>}</section>
            </aside>
          </div>

          {identity.target_record_id && <SourceFieldsMaintenance recordId={identity.target_record_id} reviewer={reviewer} />}

          <section className='panel catalog-relations' aria-labelledby='catalog-relations-title'>
            <div className='panel__head'><div><p className='eyebrow'>Estructura farmacéutica</p><h2 id='catalog-relations-title'><GitBranch size={18} aria-hidden='true' /> Relaciones y composición</h2></div></div>
            {relations.length === 0 ? <div className='catalog-relations__empty'><strong>Sin relaciones tipadas disponibles</strong><p>{identity.identity_type === 'dcp' ? 'La composición no aparece hasta que el maestro proporcione vínculos inequívocos con sustancias activas.' : 'No se ha identificado todavía el nivel anterior o siguiente sin saltar la jerarquía.'}</p></div> : <ul>{relations.map((relation) => <li key={relation.id}><button type='button' onClick={() => navigate(`/catalogo/${encodeURIComponent(relation.related_identity.id)}`)}><span className='catalog-relations__direction'>{relation.direction === 'outgoing' ? 'Hacia' : 'Desde'}{relation.ordinal ? ` · ${relation.ordinal}` : ''}</span><strong>{relation.related_identity.display_name}</strong><small>{RELATION_LABELS[relation.relation_type] ?? relation.relation_type} · {TYPE_LABELS[relation.related_identity.identity_type] ?? relation.related_identity.identity_type} · {orDash(relation.related_identity.code)}</small></button></li>)}</ul>}
          </section>

          {identity.identity_type === 'presentation' && <section className='panel catalog-classifications' aria-labelledby='catalog-classifications-title'>
            <div className='panel__head'><div><p className='eyebrow'>Clasificación farmacéutica</p><h2 id='catalog-classifications-title'>Clase comercial y condiciones</h2></div></div>
            <p className='catalog-classifications__hint'>Seleccione una única clase comercial. Las condiciones se combinan de forma independiente.</p>
            <fieldset disabled={!reviewer}>
              <legend>Clase comercial</legend>
              <div className='catalog-classifications__options'>{COMMERCIAL_CLASSES.map(([value, label]) => {
                const selected = classifications.some((item) => item.classification_type === 'commercial_class' && item.value === value && item.active)
                return <label key={value}><input type='radio' name={`commercial-${identity.id}`} checked={selected} onChange={() => void changeClassification('commercial_class', value, true)} />{label}</label>
              })}</div>
            </fieldset>
            <fieldset disabled={!reviewer}>
              <legend>Condiciones</legend>
              <div className='catalog-classifications__options'>{CONDITIONS.map(([value, label]) => {
                const selected = classifications.some((item) => item.classification_type === 'condition' && item.value === value && item.active)
                return <label key={value}><input type='checkbox' checked={selected} onChange={(event) => void changeClassification('condition', value, event.target.checked)} />{label}</label>
              })}</div>
            </fieldset>
            {!reviewer && <p className='muted'>Seleccione un revisor para cambiar clasificaciones.</p>}
            <p className='catalog-classifications__provenance'>Clasificaciones cargadas con fuente: {classifications.filter((item) => item.source_system !== 'canonical_manual').map((item) => item.source_system).filter((value, index, all) => all.indexOf(value) === index).join(', ') || 'sin clasificaciones importadas'}.</p>
          </section>}

          <section className='panel catalog-history' aria-labelledby='catalog-history-title'>
            <div className='panel__head'><div><p className='eyebrow'>Auditoría</p><h2 id='catalog-history-title'><History size={18} aria-hidden='true' /> Historial de cambios</h2></div></div>
            <ol>{[...history].reverse().map((revision) => <li key={revision.sequence}><span className='catalog-history__sequence'>v{revision.sequence}</span><div><strong>{revision.action}</strong><p>{revision.reason}</p><small>{revision.actor_id} · {formatDateTime(revision.recorded_at)}</small></div></li>)}</ol>
          </section>
        </>}
      </AsyncBoundary>
    </div>
  )
}
