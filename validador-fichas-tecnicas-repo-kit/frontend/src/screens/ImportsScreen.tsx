import { useState } from 'react'

import { fetchImport, fetchImports } from '../api/client'
import { useQuery } from '../api/useQuery'
import { AsyncBoundary } from '../components/AsyncState'
import { formatDateTime, formatNumber, orDash, shortHash } from '../domain/format'

/**
 * Consulta de los lotes de importación ya ejecutados.
 *
 * Es una pantalla de lectura: no lanza importaciones. Las filas en cuarentena y
 * los diagnósticos se muestran sin agregarlos en un único indicador de
 * «calidad», porque una fila descartada y una advertencia no son lo mismo.
 */

const STATUS_LABELS: Record<string, string> = {
  completed: 'Completada',
  pending: 'En curso',
  failed: 'Fallida',
}

function ImportDetail({ id, onClose }: { id: string; onClose: () => void }) {
  const { data, error, loading } = useQuery(() => fetchImport(id), [id])
  return (
    <section className='panel' aria-label='Detalle de la importación'>
      <div className='panel__head'>
        <h2>Detalle de la importación</h2>
        <button type='button' className='button' onClick={onClose}>
          Cerrar
        </button>
      </div>
      <AsyncBoundary loading={loading} error={error} empty={false} emptyTitle='' emptyDetail=''>
        {data && (
          <>
            <dl className='definition'>
              <div>
                <dt>Fichero</dt>
                <dd>{data.source_locator}</dd>
              </div>
              <div>
                <dt>Importador</dt>
                <dd>
                  {data.importer_name} v{data.importer_version}
                </dd>
              </div>
              <div>
                <dt>Lote</dt>
                <dd title={data.id}>
                  <code>{shortHash(data.id)}</code>
                </dd>
              </div>
              <div>
                <dt>Hash del fichero</dt>
                <dd title={data.content_hash}>
                  <code>{shortHash(data.content_hash)}</code>
                </dd>
              </div>
              <div>
                <dt>Versión declarada</dt>
                <dd>{orDash(data.source_version)}</dd>
              </div>
              <div>
                <dt>Inicio</dt>
                <dd>{formatDateTime(data.created_at)}</dd>
              </div>
              <div>
                <dt>Fin</dt>
                <dd>{formatDateTime(data.completed_at)}</dd>
              </div>
              <div>
                <dt>Filas procesadas</dt>
                <dd>{formatNumber(data.processed_rows)}</dd>
              </div>
              <div>
                <dt>Registros conservados</dt>
                <dd>{data.retained_records.toLocaleString('es-ES')}</dd>
              </div>
              <div>
                <dt>Filas en cuarentena</dt>
                <dd>{data.quarantined_rows.toLocaleString('es-ES')}</dd>
              </div>
            </dl>

            {data.sheets.length > 0 && (
              <table className='table'>
                <caption>Hojas procesadas</caption>
                <thead>
                  <tr>
                    <th scope='col'>Hoja</th>
                    <th scope='col'>Filas</th>
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
            )}

            <h3>Incidencias</h3>
            {data.incidents.length === 0 ? (
              <p className='muted'>Esta importación no registró ninguna incidencia.</p>
            ) : (
              <table className='table'>
                <thead>
                  <tr>
                    <th scope='col'>Severidad</th>
                    <th scope='col'>Código</th>
                    <th scope='col'>Mensaje</th>
                    <th scope='col'>Origen</th>
                    <th scope='col'>Casos</th>
                  </tr>
                </thead>
                <tbody>
                  {data.incidents.map((incident) => (
                    <tr key={`${incident.code}-${incident.source_locator ?? ''}`}>
                      <td>
                        <span className={`badge badge--${incident.severity}`}>
                          {incident.severity}
                        </span>
                      </td>
                      <td>
                        <code>{incident.code}</code>
                      </td>
                      <td>{incident.message}</td>
                      <td>{orDash(incident.source_locator)}</td>
                      <td>{incident.occurrence_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        )}
      </AsyncBoundary>
    </section>
  )
}

export function ImportsScreen() {
  const [selected, setSelected] = useState<string | null>(null)
  const { data, error, loading } = useQuery(() => fetchImports(), [])

  return (
    <div className='screen'>
      <div className='screen__head'>
        <div>
          <p className='eyebrow'>Importaciones</p>
          <h1>Lotes ejecutados</h1>
          <p className='lede'>
            Historial de las importaciones registradas. Esta pantalla es de consulta: no permite
            cargar ficheros desde el navegador.
          </p>
        </div>
      </div>

      <AsyncBoundary
        loading={loading}
        error={error}
        empty={(data?.items.length ?? 0) === 0}
        emptyTitle='No hay ninguna importación registrada'
        emptyDetail={
          'Todavía no se ha ejecutado ningún importador sobre esta base de datos. ' +
          'Los lotes aparecen aquí en cuanto se ejecuta una importación.'
        }
      >
        {data && (
          <table className='table'>
            <thead>
              <tr>
                <th scope='col'>Fichero</th>
                <th scope='col'>Importador</th>
                <th scope='col'>Estado</th>
                <th scope='col'>Fecha</th>
                <th scope='col'>Procesadas</th>
                <th scope='col'>Conservados</th>
                <th scope='col'>Cuarentena</th>
                <th scope='col'>Errores</th>
                <th scope='col'>
                  <span className='visually-hidden'>Acciones</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((item) => (
                <tr key={item.id}>
                  <th scope='row'>{item.source_locator}</th>
                  <td>{item.importer_name}</td>
                  <td>
                    <span className={`badge badge--${item.status}`}>
                      {STATUS_LABELS[item.status] ?? item.status}
                    </span>
                  </td>
                  <td>{formatDateTime(item.created_at)}</td>
                  <td>{formatNumber(item.processed_rows)}</td>
                  <td>{item.retained_records.toLocaleString('es-ES')}</td>
                  <td>{item.quarantined_rows.toLocaleString('es-ES')}</td>
                  <td>{item.errors}</td>
                  <td>
                    <button type='button' className='button' onClick={() => setSelected(item.id)}>
                      Ver detalle
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </AsyncBoundary>

      {selected && <ImportDetail id={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
