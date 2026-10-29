import { useEffect, useRef, useState } from 'react'
import { fetchDashboardCases, fetchDashboardExplore } from '../api/client'
import type { DashboardSegment } from '../api/types'
import { useQuery } from '../api/useQuery'
import { AsyncBoundary } from '../components/AsyncState'
import { PageHeader } from '../components/PageHeader'
import { FilterBar, FilterSelect } from '../components/FilterBar'
import { useCapability } from '../auth/SessionContext'

const number = (value: number) => value.toLocaleString('es-ES')
const percent = (count: number, total: number) => total ? `${Math.round(count * 100 / total)} %` : '—'
const PAGE_SIZE = 25

function SegmentList({ title, segments, total, prefix, onSelect }: {
  title: string
  segments: DashboardSegment[]
  total: number
  prefix: string
  onSelect: (segment: string, label: string) => void
}) {
  return (
    <section className='dashboard-explorer__group' aria-label={title}>
      <h3>{title}</h3>
      <p className='dashboard-explorer__denominator'>Sobre {number(total)} registros reales</p>
      {segments.map(item => (
        <button type='button' className='dashboard-segment' key={item.key}
          onClick={() => onSelect(`${prefix}${item.key}`, item.label)}
          aria-label={`${item.label}: ${number(item.count)} de ${number(total)} registros. Ver casos`}>
          <span className='dashboard-segment__line'><strong>{item.label}</strong><span>{number(item.count)} · {percent(item.count, total)}</span></span>
          <span className='dashboard-segment__track' aria-hidden='true'><span style={{ width: `${total ? item.count * 100 / total : 0}%` }} /></span>
        </button>
      ))}
    </section>
  )
}

function Cases({ segment, label, entityType, sourceType, onClose }: {
  segment: string
  label: string
  entityType: string
  sourceType: string
  onClose: () => void
}) {
  const [offset, setOffset] = useState(0)
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => {
    heading.current?.focus()
    heading.current?.scrollIntoView?.({ block: 'nearest' })
  }, [])
  const { data, error, loading } = useQuery(
    () => fetchDashboardCases({ segment, entityType, sourceType, offset }),
    [segment, entityType, sourceType, offset],
  )
  return (
    <section className='panel dashboard-cases' aria-label='Casos del segmento'>
      <div className='panel__head'>
        <div><p className='eyebrow'>Casos concretos</p><h2 ref={heading} tabIndex={-1}>{label}</h2></div>
        <button type='button' className='button' onClick={onClose}>Cerrar</button>
      </div>
      <AsyncBoundary loading={loading} error={error} empty={data?.total === 0}
        emptyTitle='No hay registros en este segmento' emptyDetail='Elige otro grupo o cambia los filtros.'>
        {data && <div className='dashboard-cases__body'>
          <p className='muted'>{number(data.total)} registros · {number(offset + 1)}–{number(Math.min(offset + PAGE_SIZE, data.total))}</p>
          <ul>{data.items.map(item => <li key={item.id}>
            <a href={`#/fichas/${encodeURIComponent(item.id)}`}>{item.label}</a>
            <small>{item.detail}</small>
          </li>)}</ul>
          <div className='dashboard-cases__pagination'>
            <button type='button' className='button' disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Anterior</button>
            <button type='button' className='button' disabled={offset + PAGE_SIZE >= data.total} onClick={() => setOffset(offset + PAGE_SIZE)}>Siguiente</button>
          </div>
        </div>}
      </AsyncBoundary>
    </section>
  )
}

export function DashboardScreen() {
  const canReadSources = useCapability('sources.read')
  const [entityType, setEntityType] = useState('')
  const [sourceType, setSourceType] = useState('')
  const [selected, setSelected] = useState<{ segment: string; label: string } | null>(null)
  const { data, error, loading } = useQuery(
    () => fetchDashboardExplore({ entityType, sourceType }),
    [entityType, sourceType],
  )
  const open = (segment: string, label: string) => setSelected({ segment, label })
  const priority = [
    { label: 'Trabajo abierto', value: data?.pending, unit: 'registros en cola', segment: 'pending', href: '#/trabajo' },
    { label: 'Marcados para segunda revisión', value: data?.second_review, unit: 'registros en cola', segment: 'second_review', href: '#/catalogo/segunda' },
    { label: 'Filas en cuarentena', value: data?.quarantined, unit: 'filas fuente', href: '#/datos/cuarentena' },
    { label: 'Incidencias de importación', value: data?.diagnostics, unit: 'diagnósticos agrupados', href: '#/datos/importaciones' },
  ]

  return (
    <div className='screen dashboard-screen'>
      <PageHeader eyebrow='Resumen operativo' title='Dónde actuar y qué cubren los datos'
        description='Registros reales, fuentes y trabajo de revisión. Cada cifra abre sus casos o su listado.' />
      <AsyncBoundary loading={loading} error={error}
        empty={Boolean(data && data.total_records === 0 && !entityType && !sourceType && data.quarantined === 0 && data.diagnostics === 0)}
        emptyTitle='Todavía no hay maestros importados'
        emptyDetail='El resumen se calcula sobre los registros de los maestros importados. Mientras tanto, el catálogo y las fuentes siguen disponibles.'
        emptyAction={<div className='state__actions'><a className='button button--primary' href='#/fichas'>Abrir el catálogo</a>{canReadSources && <a className='button' href='#/datos/fuentes'>Ver fuentes de datos</a>}</div>}>
        {data && <>
          <section className='dashboard-priorities' aria-label='Prioridades'>
            <h2>Atención ahora</h2>
            <div className='dashboard-priorities__grid'>
              {priority.map(item => <article className='dashboard-priority' key={item.label}>
                <p>{item.label}</p>
                <strong>{item.value === undefined ? 'No disponible' : number(item.value)}</strong>
                <span>{item.unit}</span>
                {item.segment
                  ? <button type='button' className='dashboard-priority__action' onClick={() => open(item.segment!, item.label)}>Ver casos</button>
                  : canReadSources
                    ? <a className='dashboard-priority__action' href={item.href}>Abrir listado</a>
                    : <span className='dashboard-priority__action'>Listado restringido</span>}
              </article>)}
            </div>
          </section>
          <section className='dashboard-explorer' aria-label='Explorar cobertura y calidad'>
            <div className='dashboard-explorer__head'>
              <div><h2>Cobertura y calidad</h2><p>Compare grupos y abra los registros detrás de cada barra.</p></div>
              <FilterBar label='Filtrar cobertura y calidad' activeCount={Number(Boolean(entityType)) + Number(Boolean(sourceType))}
                onClear={() => { setEntityType(''); setSourceType(''); setSelected(null) }}>
                <FilterSelect label='Tipo' name='Tipo de registro' value={entityType}
                  options={[{ value: '', label: 'Todos' }, ...data.entity_types.map(item => ({ value: item.key, label: item.label }))]}
                  onChange={value => { setEntityType(value); setSelected(null) }} />
                <FilterSelect label='Fuente' name='Fuente enlazada' value={sourceType}
                  options={[{ value: '', label: 'Todas' }, ...data.sources.map(item => ({ value: item.key, label: item.label }))]}
                  onChange={value => { setSourceType(value); setSelected(null) }} />
              </FilterBar>
            </div>
            <p className='dashboard-explorer__total'><strong>{number(data.total_records)}</strong> registros reales en la selección</p>
            {data.total_records === 0 && <p className='state state--empty'>No hay registros para estos filtros.</p>}
            <div className='dashboard-explorer__columns'>
              <SegmentList title='Tipos de registro' segments={data.entity_types} total={data.total_records} prefix='entity:' onSelect={open} />
              <SegmentList title='Estado de la cola' segments={data.review} total={data.total_records} prefix='review:' onSelect={open} />
              <section className='dashboard-explorer__group' aria-label='Cobertura documental'>
                <h3>Cobertura documental</h3>
                <p className='dashboard-explorer__denominator'>Sobre {number(data.total_records)} registros reales · una ficha puede tener varias fuentes</p>
                {data.coverage.map(item => <div key={item.key}>
                  <button type='button' className='dashboard-segment' onClick={() => open(`coverage:${item.key}`, `${item.label} disponible`)}>
                    <span className='dashboard-segment__line'><strong>{item.label}</strong><span>{number(item.count)} · {percent(item.count, data.total_records)}</span></span>
                    <span className='dashboard-segment__track' aria-hidden='true'><span style={{ width: `${data.total_records ? item.count * 100 / data.total_records : 0}%` }} /></span>
                  </button>
                  <button type='button' className='dashboard-segment__missing' onClick={() => open(`coverage:${item.key.replace(':present', ':missing')}`, `Sin ${item.label}`)}>
                    Ver {number(data.total_records - item.count)} sin {item.label.toLowerCase()}
                  </button>
                </div>)}
              </section>
            </div>
            <p className='dashboard-explorer__note'>Las filas en cuarentena y los diagnósticos pertenecen a importaciones; no se reparten por tipo de registro. Son datos de procedencia, no recomendaciones clínicas.</p>
          </section>
          {selected && <Cases key={selected.segment} segment={selected.segment} label={selected.label}
            entityType={entityType} sourceType={sourceType} onClose={() => setSelected(null)} />}
        </>}
      </AsyncBoundary>
    </div>
  )
}
