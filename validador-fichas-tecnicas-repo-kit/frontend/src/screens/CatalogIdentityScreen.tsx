import { useEffect, useState } from 'react'
import { Archive, ExternalLink, History, Save } from 'lucide-react'

import {
  fetchCatalogHistory,
  fetchCatalogIdentity,
  updateCatalogIdentity,
} from '../api/client'
import type { CatalogIdentity, CatalogRevision, Reviewer } from '../api/types'
import { AsyncBoundary } from '../components/AsyncState'
import { formatDateTime, orDash } from '../domain/format'
import { navigate } from '../navigation'

const TYPE_LABELS: Record<string, string> = {
  commercial_product: 'Producto comercial', authorization: 'Autorización',
  presentation: 'Presentación', dcpf: 'DCPF', dcp: 'DCP', dcsa: 'DCSA',
  active_ingredient: 'Sustancia activa',
}

interface Props {
  readonly identityId: string
  readonly reviewer: Reviewer | null
}

export function CatalogIdentityScreen({ identityId, reviewer }: Props) {
  const [identity, setIdentity] = useState<CatalogIdentity | null>(null)
  const [history, setHistory] = useState<CatalogRevision[]>([])
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
      const [record, revisions] = await Promise.all([
        fetchCatalogIdentity(identityId), fetchCatalogHistory(identityId),
      ])
      setIdentity(record)
      setName(record.display_name)
      setCode(record.code ?? '')
      setHistory(revisions)
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
              <section className='panel'><p className='eyebrow'>Procedencia</p><h2>Valor fuente</h2><dl className='definition'><div><dt>Sistema</dt><dd>{identity.source_system}</dd></div><div><dt>Versión</dt><dd>{identity.source_version}</dd></div><div><dt>Literal conservado</dt><dd><code>{orDash(identity.source_literal)}</code></dd></div></dl>{identity.target_record_id && <button type='button' className='button' onClick={() => navigate(`/registros/${encodeURIComponent(identity.target_record_id!)}`)}><ExternalLink size={16} aria-hidden='true' /> Ver datos importados</button>}</section>
            </aside>
          </div>

          <section className='panel catalog-history' aria-labelledby='catalog-history-title'>
            <div className='panel__head'><div><p className='eyebrow'>Auditoría</p><h2 id='catalog-history-title'><History size={18} aria-hidden='true' /> Historial de cambios</h2></div></div>
            <ol>{[...history].reverse().map((revision) => <li key={revision.sequence}><span className='catalog-history__sequence'>v{revision.sequence}</span><div><strong>{revision.action}</strong><p>{revision.reason}</p><small>{revision.actor_id} · {formatDateTime(revision.recorded_at)}</small></div></li>)}</ol>
          </section>
        </>}
      </AsyncBoundary>
    </div>
  )
}
