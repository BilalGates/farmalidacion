import { useCallback, useEffect, useRef, useState, type CSSProperties } from 'react'
import { ArrowRight, Search } from 'lucide-react'
import { fetchRealRecords } from '../api/client'
import type { Reviewer, ReviewState, TargetRecord } from '../api/types'
import { useQuery } from '../api/useQuery'
import { ReviewBadge } from '../components/StateBadge'
import { REVIEW_STATE_LABELS } from '../domain/vocabulary'
import { navigate } from '../navigation'
import { ReviewScreen } from './ReviewScreen'
import './records-workspace.css'

const PAGE_SIZE = 50
const TYPES: Record<string, string> = { medication: 'Medicamento', specialty: 'Especialidad', active_ingredient: 'Principio activo' }
const RESOLVED = new Set(['confirmado', 'corregido', 'no_consta', 'no_aplica', 'descartado'])
const STATES: ReviewState[] = ['pendiente', 'en_revision', 'validado']

/** Listado y revisión comparten montaje: cambiar el hash no pierde los filtros. */
export function RecordsWorkspace({ recordId, reviewer = null }: { recordId?: string; reviewer?: Reviewer | null }) {
  const [term, setTerm] = useState('')
  const [query, setQuery] = useState('')
  const [estado, setEstado] = useState<ReviewState | ''>('pendiente')
  const [offset, setOffset] = useState(0)
  const [retry, setRetry] = useState(0)
  const [busy, setBusy] = useState(false)
  const [seeking, setSeeking] = useState(false)
  const [notice, setNotice] = useState('')
  const [listWidth, setListWidth] = useState(22)
  const [sourceWidth, setSourceWidth] = useState(43)
  const [observedStates, setObservedStates] = useState<Record<string, ReviewState>>({})
  const searchGeneration = useRef(0)
  const knownNames = useRef(new Map<string, string | null>())
  const rootRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const measure = () => rootRef.current?.style.setProperty('--records-top', `${rootRef.current.getBoundingClientRect().top + window.scrollY}px`)
    measure()
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(measure)
    const header = document.querySelector('.topbar')
    if (header) observer?.observe(header)
    window.addEventListener('resize', measure)
    return () => { observer?.disconnect(); window.removeEventListener('resize', measure) }
  }, [])
  const { data, error, loading } = useQuery(() => fetchRealRecords({
    origin: 'real', q: query || undefined, estado: estado || undefined, limit: PAGE_SIZE, offset,
  }), [query, estado, offset, retry])
  useEffect(() => { data?.items.forEach(item => knownNames.current.set(item.id, item.display_name)) }, [data])

  // Una búsqueda de siguiente pendiente nunca puede seleccionar sobre filtros nuevos.
  useEffect(() => { searchGeneration.current += 1; setSeeking(false); setNotice('')
    return () => { searchGeneration.current += 1 }
  }, [query, estado, offset, recordId])
  const selectedId = recordId
  const selectedItem = data?.items.find(item => item.id === selectedId)
  const onRecordChange = useCallback((record: TargetRecord) => {
    const values = record.blocks.flatMap(block => block.values)
    const count = values.filter(value => RESOLVED.has(value.validation_state)).length
    const state: ReviewState = !count ? 'pendiente' : count === values.length ? 'validado' : 'en_revision'
    setObservedStates(previous => previous[record.id] === state ? previous : { ...previous, [record.id]: state })
  }, [])

  function select(id: string) { if (!busy && !seeking) navigate(`/fichas/${encodeURIComponent(id)}`) }
  async function nextPending() {
    if (!data || busy || loading || seeking) return
    const generation = ++searchGeneration.current
    setSeeking(true); setNotice('')
    try {
      const currentPage = estado && estado !== 'pendiente'
        ? await fetchRealRecords({ origin: 'real', q: query || undefined, limit: PAGE_SIZE, offset })
        : data
      if (generation !== searchGeneration.current) return
      const start = currentPage.items.findIndex(item => item.id === selectedId)
      const next = currentPage.items.slice(start + 1).find(item => (observedStates[item.id] ?? item.review_state) === 'pendiente')
      if (next) {
        if (estado && estado !== 'pendiente') setEstado('pendiente')
        navigate(`/fichas/${encodeURIComponent(next.id)}`); return
      }
      // La API filtra estado después de paginar. total no es un total de pendientes.
      for (let pageOffset = offset + PAGE_SIZE; pageOffset < data.total; pageOffset += PAGE_SIZE) {
        setNotice('Buscando el siguiente pendiente…')
        const page = await fetchRealRecords({ origin: 'real', q: query || undefined, estado: 'pendiente', limit: PAGE_SIZE, offset: pageOffset })
        if (generation !== searchGeneration.current) return
        const candidate = page.items.find(item => (observedStates[item.id] ?? item.review_state) === 'pendiente')
        if (candidate) {
          setEstado('pendiente'); setOffset(pageOffset)
          navigate(`/fichas/${encodeURIComponent(candidate.id)}`)
          return
        }
      }
      setNotice('No hay más registros pendientes después de esta posición para esta búsqueda.')
    } catch (cause) {
      if (generation === searchGeneration.current) setNotice(cause instanceof Error ? cause.message : 'No se pudo buscar el siguiente pendiente.')
    } finally { if (generation === searchGeneration.current) setSeeking(false) }
  }

  return <div ref={rootRef} className='screen records-workspace' style={{ '--records-list-width': `${listWidth}%`, '--records-source-width': `${sourceWidth}%` } as CSSProperties}>
    <header className='records-heading'>
      <div><p className='eyebrow'>Revisión</p><h1>Registros</h1><p className='muted'>Selecciona, revisa y continúa con el siguiente pendiente.</p></div>
      <details className='records-layout-settings'><summary>Ajustar columnas</summary>
        <label>Listado · {listWidth}%<input type='range' min='18' max='28' value={listWidth} onChange={event => setListWidth(Number(event.target.value))} /></label>
        <label>Fuente en la revisión · {sourceWidth}%<input type='range' min='35' max='50' value={sourceWidth} onChange={event => setSourceWidth(Number(event.target.value))} /></label>
      </details>
    </header>
    <div className='records-split'>
      <aside className='records-browser' aria-label='Listado de registros'>
        <div className='records-browser__head'>
          <h2>Registros del maestro <span className='records-origin'>Real</span></h2>
          <form role='search' onSubmit={event => { event.preventDefault(); setOffset(0); setQuery(term.trim()) }}>
            <label className='visually-hidden' htmlFor='records-search'>Buscar por descripción o identificador del maestro</label>
            <div className='records-search'><input id='records-search' type='search' value={term} onChange={event => setTerm(event.target.value)} placeholder='Nombre o identificador' disabled={busy} />
              <button type='submit' className='button' aria-label='Buscar' disabled={busy}><Search size={16} aria-hidden='true' /></button></div>
          </form>
          <label className='field'><span className='field__label'>Estado de revisión</span><select value={estado} disabled={busy} onChange={event => { setEstado(event.target.value as ReviewState | ''); setOffset(0) }}>
            <option value=''>Todos</option>{STATES.map(state => <option key={state} value={state}>{REVIEW_STATE_LABELS[state]}</option>)}
          </select></label>
          {data && <p className='records-count'>{estado ? `${data.items.length} en esta página` : `${data.total.toLocaleString('es-ES')} registros`} · página {Math.floor(offset / PAGE_SIZE) + 1} de {Math.max(1, Math.ceil(data.total / PAGE_SIZE))}</p>}
        </div>
        <div className='records-browser__list' aria-busy={loading}>
          {loading ? <p className='records-empty' role='status'>Cargando registros…</p> : error ? <div className='records-empty' role='alert'><p>{error}</p><button className='button' onClick={() => setRetry(value => value + 1)}>Reintentar</button></div> : !data?.items.length ? <div className='records-empty'><p>{data?.total === 0 && query ? 'La búsqueda no devuelve resultados' : 'No hay coincidencias en esta página.'}</p><p>{query ? `Búsqueda: «${query}». ` : ''}Puedes cambiar los filtros o continuar a la siguiente página.</p></div> : data.items.map(item => <button key={item.id} type='button' className='records-item' disabled={busy || seeking} aria-pressed={selectedId === item.id} onClick={() => select(item.id)}>
            <span className='records-item__name'>{item.display_name || 'Sin descripción'}</span>
            <span className='records-item__identifier'>{item.identifier || item.id}</span>
            <span className='records-item__meta'>{TYPES[item.entity_type] ?? item.entity_type} · {item.block_count} bloques · {item.field_count} campos</span>
            <ReviewBadge state={observedStates[item.id] ?? item.review_state} />
          </button>)}
        </div>
        <nav className='records-pagination' aria-label='Páginas de registros'>
          <button type='button' className='button' disabled={busy || seeking || loading || offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Anterior</button>
          <button type='button' className='button' disabled={busy || seeking || loading || !data || offset + PAGE_SIZE >= data.total} onClick={() => setOffset(offset + PAGE_SIZE)}>Siguiente</button>
        </nav>
      </aside>
      <section className='records-detail' aria-label='Revisión del registro seleccionado'>
        {selectedId ? <ReviewScreen key={selectedId} recordId={selectedId} reviewer={reviewer} compact displayName={selectedItem?.display_name ?? knownNames.current.get(selectedId)} onBusyChange={setBusy} onRecordChange={onRecordChange} /> : <div className='records-welcome'><h2>Tu espacio de revisión</h2><p>Selecciona un registro para consultar sus campos y su fuente original.</p></div>}
      </section>
    </div>
    <footer className='records-footer'>
      <span role='status'>{notice || (busy ? 'Guardando decisión…' : 'Los borradores se conservan en este navegador. Las decisiones se firman al guardar.')}</span>
      {seeking ? <button className='button' onClick={() => { searchGeneration.current += 1; setSeeking(false); setNotice('Búsqueda detenida.') }}>Detener búsqueda</button> : <button type='button' className='button button--primary' onClick={() => void nextPending()} disabled={busy || loading || !data}>Siguiente pendiente <ArrowRight size={16} aria-hidden='true' /></button>}
    </footer>
  </div>
}
