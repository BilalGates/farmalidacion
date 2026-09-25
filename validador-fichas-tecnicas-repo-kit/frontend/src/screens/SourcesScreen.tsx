import { Fragment, useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'

import { fetchSource, fetchSources } from '../api/client'
import type { SourceSummary } from '../api/types'
import { useQuery } from '../api/useQuery'
import { AsyncBoundary } from '../components/AsyncState'
import { formatDateTime, orDash, shortHash } from '../domain/format'

/**
 * Fuentes realmente conocidas por el sistema.
 *
 * No se enumeran las fuentes previstas por el producto, sino los documentos que
 * existen en la base de datos. Una fuente que el proyecto contempla pero que
 * nunca se ha cargado no aparece aquí: aparecería como «disponible» sin serlo.
 */

const SOURCE_TYPE_LABELS: Record<string, string> = {
  master_excel: 'Maestro Excel',
  demo_showcase: 'Conjunto DEMO',
  cima: 'CIMA',
  ficha_tecnica: 'Ficha técnica',
  cima_document_type_1: 'CIMA · Ficha técnica',
  cima_document_type_2: 'CIMA · Prospecto',
}

const STATUS_LABELS: Record<string, string> = {
  disponible: 'Disponible',
  con_errores: 'Con errores',
  sin_datos: 'Sin datos',
}

const STATUS_PRIORITY: Record<string, number> = {
  disponible: 0,
  sin_datos: 1,
  con_errores: 2,
}

interface SourceGroup {
  sourceType: string
  label: string
  items: SourceSummary[]
  status: string
  records: number
  batches: number
  incidents: number
  lastUpdatedAt: string | null
}

export function groupSources(items: SourceSummary[]): SourceGroup[] {
  const grouped = new Map<string, SourceSummary[]>()
  items.forEach((item) => grouped.set(item.source_type, [...(grouped.get(item.source_type) ?? []), item]))

  return [...grouped.entries()].map(([sourceType, groupItems]) => ({
    sourceType,
    label: SOURCE_TYPE_LABELS[sourceType] ?? sourceType,
    items: groupItems,
    status: groupItems.reduce((worst, item) =>
      (STATUS_PRIORITY[item.status] ?? 1) > (STATUS_PRIORITY[worst] ?? 1) ? item.status : worst,
    groupItems[0].status),
    records: groupItems.reduce((total, item) => total + item.records, 0),
    batches: groupItems.reduce((total, item) => total + item.batches, 0),
    incidents: groupItems.reduce(
      (total, item) => total + item.diagnostics + item.quarantined_rows,
      0,
    ),
    lastUpdatedAt: groupItems.reduce<string | null>((latest, item) => {
      if (!item.last_updated_at) return latest
      return !latest || item.last_updated_at > latest ? item.last_updated_at : latest
    }, null),
  }))
}

function SourceDetail({ id, onClose }: { id: string; onClose: () => void }) {
  const { data, error, loading } = useQuery(() => fetchSource(id), [id])
  return (
    <section className='panel' aria-label='Detalle de la fuente'>
      <div className='panel__head'>
        <h2>Detalle de la fuente</h2>
        <button type='button' className='button' onClick={onClose}>
          Cerrar
        </button>
      </div>
      <AsyncBoundary
        loading={loading}
        error={error}
        empty={false}
        emptyTitle=''
        emptyDetail=''
      >
        {data && (
          <>
            <dl className='definition'>
              <div>
                <dt>Nombre</dt>
                <dd>{data.name}</dd>
              </div>
              <div>
                <dt>Tipo</dt>
                <dd>{SOURCE_TYPE_LABELS[data.source_type] ?? data.source_type}</dd>
              </div>
              <div>
                <dt>Versiones documentales</dt>
                <dd>{data.versions}</dd>
              </div>
              <div>
                <dt>Versión declarada</dt>
                <dd>{orDash(data.latest_version)}</dd>
              </div>
              <div>
                <dt>Hash de contenido</dt>
                <dd title={data.latest_content_hash ?? undefined}>
                  <code>{shortHash(data.latest_content_hash)}</code>
                </dd>
              </div>
              <div>
                <dt>Última actualización</dt>
                <dd>{formatDateTime(data.last_updated_at)}</dd>
              </div>
              <div>
                <dt>Registros enlazados</dt>
                <dd>{data.records.toLocaleString('es-ES')}</dd>
              </div>
              <div>
                <dt>Incidencias</dt>
                <dd>{data.diagnostics}</dd>
              </div>
            </dl>

            {data.sheets.length > 0 ? (
              <table className='table'>
                <caption>Hojas importadas</caption>
                <thead>
                  <tr>
                    <th scope='col'>Hoja</th>
                    <th scope='col'>Filas de datos</th>
                    <th scope='col'>Valores con contenido</th>
                  </tr>
                </thead>
                <tbody>
                  {data.sheets.map((sheet) => (
                    <tr key={sheet.sheet_ordinal}>
                      <th scope='row'>{sheet.sheet_name}</th>
                      <td>{sheet.data_row_count.toLocaleString('es-ES')}</td>
                      <td>{sheet.material_value_count.toLocaleString('es-ES')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className='muted'>
                Esta fuente no registra hojas importadas: no procede de un libro Excel.
              </p>
            )}
          </>
        )}
      </AsyncBoundary>
    </section>
  )
}

export function SourcesScreen() {
  const [selected, setSelected] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const { data, error, loading } = useQuery(() => fetchSources(), [])

  const toggleGroup = (sourceType: string) => {
    setExpanded((current) => {
      const next = new Set(current)
      if (next.has(sourceType)) next.delete(sourceType)
      else next.add(sourceType)
      return next
    })
  }

  return (
    <div className='screen'>
      <div className='screen__head'>
        <div>
          <p className='eyebrow'>Fuentes</p>
          <h1>Fuentes de datos cargadas</h1>
          <p className='lede'>
            Los documentos se agrupan por origen. Despliega un grupo para consultar cada documento,
            su versión y su hash de contenido.
          </p>
        </div>
      </div>

      <AsyncBoundary
        loading={loading}
        error={error}
        empty={(data?.items.length ?? 0) === 0}
        emptyTitle='No hay ninguna fuente cargada'
        emptyDetail={
          'No existe ningún documento de origen en la base de datos. Las fuentes aparecen ' +
          'aquí cuando una importación las registra.'
        }
      >
        {data && (
          <table className='table'>
            <thead>
              <tr>
                <th scope='col'>Fuente</th>
                <th scope='col'>Tipo</th>
                <th scope='col'>Estado</th>
                <th scope='col'>Versión</th>
                <th scope='col'>Registros</th>
                <th scope='col'>Lotes</th>
                <th scope='col'>Incidencias</th>
                <th scope='col'>Actualizada</th>
                <th scope='col'>
                  <span className='visually-hidden'>Acciones</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {groupSources(data.items).map((group) => {
                const isExpanded = expanded.has(group.sourceType)
                return (
                  <Fragment key={group.sourceType}>
                    <tr className='source-group'>
                      <th scope='row'>
                        <button
                          type='button'
                          className='source-group__toggle'
                          aria-expanded={isExpanded}
                          onClick={() => toggleGroup(group.sourceType)}
                        >
                          {isExpanded ? <ChevronDown aria-hidden='true' /> : <ChevronRight aria-hidden='true' />}
                          <span>{group.label}</span>
                          <span className='source-group__count'>{group.items.length} documentos</span>
                        </button>
                      </th>
                      <td>{group.label}</td>
                      <td><span className={`badge badge--${group.status}`}>{STATUS_LABELS[group.status] ?? group.status}</span></td>
                      <td>—</td>
                      <td>{group.records.toLocaleString('es-ES')}</td>
                      <td>{group.batches}</td>
                      <td>{group.incidents}</td>
                      <td>{formatDateTime(group.lastUpdatedAt)}</td>
                      <td />
                    </tr>
                    {isExpanded && group.items.map((item) => (
                      <tr key={item.key} className='source-group__child'>
                        <th scope='row'>{item.name}</th>
                        <td>{SOURCE_TYPE_LABELS[item.source_type] ?? item.source_type}</td>
                        <td>
                          <span className={`badge badge--${item.status}`}>
                            {STATUS_LABELS[item.status] ?? item.status}
                          </span>
                        </td>
                        <td>{orDash(item.latest_version)}</td>
                        <td>{item.records.toLocaleString('es-ES')}</td>
                        <td>{item.batches}</td>
                        <td>{item.diagnostics + item.quarantined_rows}</td>
                        <td>{formatDateTime(item.last_updated_at)}</td>
                        <td>
                          <button type='button' className='button' onClick={() => setSelected(item.key)}>
                            Ver detalle
                          </button>
                        </td>
                      </tr>
                    ))}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        )}
      </AsyncBoundary>

      {selected && <SourceDetail id={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
