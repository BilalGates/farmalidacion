import { useState } from 'react'

import { fetchSource, fetchSources } from '../api/client'
import { useQuery } from '../api/useQuery'
import { AsyncBoundary } from '../components/AsyncState'
import { PageHeader } from '../components/PageHeader'
import { formatDateTime, orDash, shortHash } from '../domain/format'
import { openCatalogSource } from '../domain/catalogSourceNavigation'
import type { CatalogSourceWorkbook } from '../api/types'

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

const WORKBOOK_PREVIEWS: Record<string, {
  view: CatalogSourceWorkbook
  title: string
  description: string
  action: string
  sheets: Record<string, string>
}> = {
  'Especialidades-CargaMaster190626.xlsx': {
    view: 'especialidades', title: 'Especialidades y presentaciones',
    description: 'Cada registro principal identifica una presentación mediante su Código Nacional. Los excipientes se conservan como ocurrencias separadas.',
    action: 'Explorar presentaciones',
    sheets: { General: 'Presentaciones y códigos nacionales', Excipientes: 'Excipientes por presentación' },
  },
  'Medicamento-cargaMaster25062026.xlsx': {
    view: 'medicamentos', title: 'Medicamentos',
    description: 'La ficha del medicamento conserva composición, indicaciones, vías y enlaces en hojas y ocurrencias distintas.',
    action: 'Explorar medicamentos',
    sheets: {
      General: 'Identidad y datos generales', Composicion: 'Componentes y cantidades',
      Indicacion: 'Indicaciones', Frecuencia: 'Frecuencias', Via: 'Vías de administración',
      Prescripcion: 'Prescripción', Links: 'Enlaces relacionados',
    },
  },
  'PrincipioActivoCargaMaster-22062026.xlsx': {
    view: 'principios_activos', title: 'Principios activos',
    description: 'La identidad del principio activo y sus datos complementarios se consultan por hoja sin mezclarlos con medicamentos o presentaciones.',
    action: 'Explorar principios activos',
    sheets: {
      General: 'Identidad del principio activo', Frecuencia: 'Frecuencias',
      Via: 'Vías de administración', ConsejosAdministracion: 'Consejos de administración',
      DatosAnaliticos: 'Datos analíticos',
    },
  },
}

function SourceDetail({ id, onClose }: { id: string; onClose: () => void }) {
  const { data, error, loading } = useQuery(() => fetchSource(id), [id])
  const preview = data?.source_type === 'master_excel' ? WORKBOOK_PREVIEWS[data.name] : undefined
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
            {preview && <div className={`source-workbook-preview source-workbook-preview--${preview.view}`}>
              <p className='eyebrow'>Vista del libro maestro</p>
              <h3>{preview.title}</h3>
              <p>{preview.description}</p>
              <p>Abra un registro para consultar todas sus hojas y anotar o corregir valores con revisor y motivo. El Excel original se conserva.</p>
              <button type='button' className='button button--primary' onClick={() => openCatalogSource(preview.view)}>
                {preview.action}
              </button>
            </div>}
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
              <div className='table-wrap' role='region' aria-label='Hojas del libro; desplazamiento horizontal disponible' tabIndex={0}>
              <table className='table'>
                <caption>Hojas importadas</caption>
                <thead>
                  <tr>
                    <th scope='col'>Hoja</th>
                    <th scope='col'>Contenido</th>
                    <th scope='col'>Filas de datos</th>
                    <th scope='col'>Valores con contenido</th>
                  </tr>
                </thead>
                <tbody>
                  {data.sheets.map((sheet) => (
                    <tr key={sheet.sheet_ordinal}>
                      <th scope='row'>{sheet.sheet_name}</th>
                      <td>{preview?.sheets[sheet.sheet_name] ?? 'Hoja de origen'}{sheet.data_row_count === 0 ? ' · solo cabecera' : ''}</td>
                      <td>{sheet.data_row_count.toLocaleString('es-ES')}</td>
                      <td>{sheet.material_value_count.toLocaleString('es-ES')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
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
      <PageHeader eyebrow='Fuentes' title='Fuentes de datos cargadas' description='Cada fila es un documento de origen presente en la base de datos, con su versión y su hash de contenido. Sólo aparece lo que se ha cargado realmente.' />

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
          <div className='table-wrap' role='region' aria-label='Fuentes; desplazamiento horizontal disponible' tabIndex={0}>
          <table className='table'>
            <thead>
              <tr>
                <th scope='col'>Fuente</th>
                <th scope='col'>Tipo</th>
                <th scope='col'>Estado</th>
                <th scope='col'>Versión</th>
                <th scope='col' className='cell--num'>Registros</th>
                <th scope='col' className='cell--num'>Lotes</th>
                <th scope='col' className='cell--num'>Incidencias</th>
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
                  <td className='cell--num'>{item.records.toLocaleString('es-ES')}</td>
                  <td className='cell--num'>{item.batches}</td>
                  <td className='cell--num'>{item.diagnostics + item.quarantined_rows}</td>
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
          </div>
        )}
      </AsyncBoundary>

      {selected && <SourceDetail id={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
