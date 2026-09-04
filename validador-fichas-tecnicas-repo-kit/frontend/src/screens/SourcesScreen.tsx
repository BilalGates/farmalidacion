import { useState } from 'react'

import { fetchSource, fetchSources } from '../api/client'
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
}

const STATUS_LABELS: Record<string, string> = {
  disponible: 'Disponible',
  con_errores: 'Con errores',
  sin_datos: 'Sin datos',
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
  const { data, error, loading } = useQuery(() => fetchSources(), [])

  return (
    <div className='screen'>
      <div className='screen__head'>
        <div>
          <p className='eyebrow'>Fuentes</p>
          <h1>Fuentes de datos cargadas</h1>
          <p className='lede'>
            Cada fila es un documento de origen presente en la base de datos, con su versión y su
            hash de contenido. Sólo aparece lo que se ha cargado realmente.
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
              {data.items.map((item) => (
                <tr key={item.key}>
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
                    <button
                      type='button'
                      className='button'
                      onClick={() => setSelected(item.key)}
                    >
                      Ver detalle
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </AsyncBoundary>

      {selected && <SourceDetail id={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
