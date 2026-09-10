import { useState } from 'react'
import { Activity, AlertCircle, ArrowDownLeft, ArrowRight, ArrowUpRight, CheckCircle2, ChevronDown, ChevronUp, FilePenLine, History, RotateCcw } from 'lucide-react'
import './maintenance.css'

import { fetchMaintenanceChange, fetchMaintenanceChanges, fetchMaintenanceRuns, type MaintenanceChangeSummary } from '../api/client'
import { useQuery } from '../api/useQuery'
import { AsyncBoundary } from '../components/AsyncState'
import { formatDateTime, shortHash } from '../domain/format'

const CHANGE_LABELS: Record<number, string> = { 1: 'Alta', 2: 'Baja', 3: 'Modificación' }
const AREA_LABELS: Record<string, string> = { ft: 'Ficha técnica', estado: 'Estado de autorización', comercializacion: 'Comercialización' }
const areaLabel = (area: string) => AREA_LABELS[area.toLowerCase()] ?? area.replaceAll('_', ' ')

function ChangeDetail({ eventId }: { eventId: string }) {
  const { data, error, loading } = useQuery(() => fetchMaintenanceChange(eventId), [eventId])
  return <AsyncBoundary loading={loading} error={error} empty={false} emptyTitle='Sin detalle' emptyDetail='La novedad no contiene información adicional.'>
    {data && <section className='maintenance-detail' aria-label='Detalle de la novedad'>
      <div className='maintenance-detail__head'><div><p className='eyebrow'>Evidencia documental</p><h3>Cambios en la ficha técnica</h3></div><code title={data.source_sha256}>{shortHash(data.source_sha256)}</code></div>
      {data.diff === null ? <p className='state state--empty'>CIMA comunicó el cambio, pero no hay una nueva versión de ficha que comparar.</p>
        : data.diff.changes.length === 0 ? <p className='state state--empty'>Las versiones no presentan diferencias por apartado.</p>
        : <div className='maintenance-diff-list'>{data.diff.changes.map((change) => <article key={`${change.role}-${change.ordinal}`}>
          <div><span>Apartado</span><strong>{change.new_locator ?? change.old_locator ?? change.role}</strong></div>
          <span className='maintenance-type maintenance-type--3'>{change.change_type}</span>
          <pre className='maintenance-diff'>{change.text_diff ?? change.diff_kind}</pre>
        </article>)}</div>}
    </section>}
  </AsyncBoundary>
}

interface ChangeGroup { nregistro: string; events: MaintenanceChangeSummary[]; reopened: number; areas: string[] }

function groupChanges(data: MaintenanceChangeSummary[]): ChangeGroup[] {
  const grouped = new Map<string, MaintenanceChangeSummary[]>()
  data.forEach((item) => grouped.set(item.nregistro, [...(grouped.get(item.nregistro) ?? []), item]))
  return [...grouped].map(([nregistro, events]) => ({
    nregistro, events,
    reopened: events.reduce((total, item) => total + item.affected_field_count, 0),
    areas: [...new Set(events.flatMap((item) => item.areas))],
  })).sort((a, b) => b.reopened - a.reopened || b.events[0].occurred_at_epoch - a.events[0].occurred_at_epoch)
}

function ChangeCard({ group, selected, onSelect }: { group: ChangeGroup; selected: string | null; onSelect: (id: string) => void }) {
  const latest = group.events[0]
  const eventToShow = group.events.find((item) => item.has_diff) ?? latest
  const open = selected === eventToShow.id
  return <article className={`change-card${group.reopened ? ' change-card--attention' : ''}`}>
    <div className='change-card__top'>
      <div className='change-card__identity'><span className='change-card__icon'>{group.reopened ? <AlertCircle aria-hidden='true' /> : <CheckCircle2 aria-hidden='true' />}</span><div><p>{group.reopened ? 'Requiere tu atención' : 'Novedad informativa'}</p><h3>Registro CIMA {group.nregistro}</h3></div></div>
      <span className={`maintenance-type maintenance-type--${latest.change_type}`}>{CHANGE_LABELS[latest.change_type] ?? `Tipo ${latest.change_type}`}</span>
    </div>
    <p className='change-card__explanation'>{group.reopened ? `Un cambio de CIMA ha dejado ${group.reopened} ${group.reopened === 1 ? 'campo pendiente' : 'campos pendientes'} de revisión.` : `CIMA ha comunicado ${group.events.length === 1 ? 'una novedad' : `${group.events.length} novedades`} sin reabrir campos ya validados.`}</p>
    <div className='change-card__facts'>
      <div><span>Qué ha cambiado</span><strong>{group.areas.length ? group.areas.map(areaLabel).join(' · ') : 'Área no especificada'}</strong></div>
      <div><span>Actividad</span><strong>{group.events.length} {group.events.length === 1 ? 'evento' : 'eventos'}</strong></div>
      <div><span>Último cambio</span><strong>{formatDateTime(latest.recorded_at)}</strong></div>
    </div>
    <div className='change-card__actions'>
      {eventToShow.has_diff ? <button type='button' className='button button--primary' aria-expanded={open} onClick={() => onSelect(eventToShow.id)}>{open ? <ChevronUp aria-hidden='true' /> : <ChevronDown aria-hidden='true' />}{open ? 'Ocultar diferencias' : 'Ver qué ha cambiado'}</button> : <span className='change-card__no-diff'>Sin comparación documental disponible</span>}
      <span>N.º de registro {group.nregistro}</span>
    </div>
    {open && <ChangeDetail eventId={eventToShow.id} />}
  </article>
}

export function MaintenanceScreen() {
  const [selected, setSelected] = useState<string | null>(null)
  const [historyOpen, setHistoryOpen] = useState(false)
  const { data, error, loading } = useQuery(() => fetchMaintenanceChanges(), [])
  const { data: runs } = useQuery(() => fetchMaintenanceRuns(), [])
  const latestRun = runs?.[0]
  const groups = data ? groupChanges(data) : []
  const attention = groups.filter((item) => item.reopened > 0)
  const informative = groups.filter((item) => item.reopened === 0)
  const reopened = groups.reduce((total, item) => total + item.reopened, 0)
  const count = (type: number) => data?.filter((item) => item.change_type === type).length ?? 0

  return <div className='screen maintenance-screen'>
    <header className='maintenance-hero'><div><p className='eyebrow'>Cambios en tu catálogo</p><h1>¿Qué ha cambiado en CIMA?</h1><p>Resumen de novedades regulatorias y del trabajo que requieren en Farmalidación.</p></div>{latestRun && <div className='maintenance-last-check'><RotateCcw aria-hidden='true' /><span><small>Última consulta</small><strong>{latestRun.requested_date}</strong></span></div>}</header>
    {latestRun?.status === 'failed' && <div className='state state--error' role='alert'><p className='state__title'>La última consulta CIMA falló</p><p className='state__detail'>{latestRun.requested_date} · intento {latestRun.attempt}: {latestRun.error_detail}</p></div>}
    <AsyncBoundary loading={loading} error={error} empty={data !== null && data.length === 0} emptyTitle='Tu catálogo está al día' emptyDetail='CIMA no ha comunicado novedades en las consultas registradas.'>
      {data && data.length > 0 && <>
        <section className='maintenance-story' aria-label='Resumen de novedades'>
          <div className='maintenance-story__main'><span className='maintenance-story__icon'><Activity aria-hidden='true' /></span><div><p>Situación actual</p><strong>{attention.length ? `${attention.length} ${attention.length === 1 ? 'medicamento requiere' : 'medicamentos requieren'} revisión` : 'No hay revisiones nuevas pendientes'}</strong><span>{reopened ? `${reopened} campos se han reabierto por cambios documentales.` : 'Los cambios recibidos son informativos.'}</span></div>{attention.length > 0 && <ArrowRight aria-hidden='true' />}</div>
          <div className='maintenance-story__metric'><FilePenLine aria-hidden='true' /><span><strong>{count(3)}</strong> modificaciones</span></div><div className='maintenance-story__metric'><ArrowUpRight aria-hidden='true' /><span><strong>{count(1)}</strong> altas</span></div><div className='maintenance-story__metric'><ArrowDownLeft aria-hidden='true' /><span><strong>{count(2)}</strong> bajas</span></div>
        </section>
        {attention.length > 0 && <section className='maintenance-section' aria-labelledby='attention-title'><div className='maintenance-section__head'><div><p className='eyebrow'>Prioridad</p><h2 id='attention-title'>Necesitan revisión</h2><p>Estos cambios han reabierto decisiones anteriores. Revisa el documento y confirma si siguen siendo válidas.</p></div><span className='maintenance-count'>{attention.length}</span></div><div className='change-card-list'>{attention.map((group) => <ChangeCard key={group.nregistro} group={group} selected={selected} onSelect={(id) => setSelected(selected === id ? null : id)} />)}</div></section>}
        {informative.length > 0 && <section className='maintenance-section' aria-labelledby='information-title'><div className='maintenance-section__head'><div><p className='eyebrow'>Seguimiento</p><h2 id='information-title'>Cambios informativos</h2><p>Novedades que conviene conocer y que no han reabierto campos validados.</p></div><span className='maintenance-count maintenance-count--quiet'>{informative.length}</span></div><div className='change-card-list'>{informative.map((group) => <ChangeCard key={group.nregistro} group={group} selected={selected} onSelect={(id) => setSelected(selected === id ? null : id)} />)}</div></section>}
        <section className='maintenance-history'><button type='button' className='maintenance-history__toggle' aria-expanded={historyOpen} onClick={() => setHistoryOpen(!historyOpen)}><span><History aria-hidden='true' /><span><strong>Historial técnico</strong><small>{data.length} eventos individuales registrados</small></span></span>{historyOpen ? <ChevronUp aria-hidden='true' /> : <ChevronDown aria-hidden='true' />}</button>{historyOpen && <div className='maintenance-table-wrap'><table className='table'><thead><tr><th>Registrada</th><th>N.º registro</th><th>Tipo</th><th>Áreas</th><th>Impacto</th></tr></thead><tbody>{data.map((item) => <tr key={item.id}><th scope='row'>{formatDateTime(item.recorded_at)}</th><td className='cell--mono'>{item.nregistro}</td><td>{CHANGE_LABELS[item.change_type]}</td><td>{item.areas.map(areaLabel).join(', ') || 'No especificada'}</td><td>{item.affected_field_count ? `${item.affected_field_count} campos reabiertos` : 'Sin reapertura'}</td></tr>)}</tbody></table></div>}</section>
      </>}
    </AsyncBoundary>
  </div>
}
