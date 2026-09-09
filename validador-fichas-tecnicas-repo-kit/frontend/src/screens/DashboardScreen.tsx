import { fetchDashboard } from '../api/client'
import { useQuery } from '../api/useQuery'
import { AsyncBoundary } from '../components/AsyncState'
import { formatDateTime } from '../domain/format'

/**
 * Panel de inicio con cifras reales del sistema.
 *
 * Ninguna cifra está escrita en la interfaz: todas llegan del backend. Si una
 * métrica no puede calcularse, el backend no la envía y aquí no aparece, en
 * lugar de mostrar un cero que se leería como «no hay datos».
 */

const STATUS_LABELS: Record<string, string> = {
  disponible: 'Disponible',
  parcial: 'Parcial',
  pendiente: 'Pendiente',
}

export function DashboardScreen() {
  const { data, error, loading } = useQuery(() => fetchDashboard(), [])

  return (
    <div className='screen'>
      <div className='screen__head'>
        <div>
          <p className='eyebrow'>Resumen operativo</p>
          <h1>Estado de la validación</h1>
          <p className='lede'>
            Una vista rápida del trabajo almacenado y de la disponibilidad de cada etapa.
          </p>
        </div>
        <div className='dashboard-freshness'>
          <span className='dashboard-freshness__dot' aria-hidden='true' />
          <span>
            <strong>Datos actualizados</strong>
            <small>{data?.last_import_at ? formatDateTime(data.last_import_at) : 'Sin importaciones'}</small>
          </span>
        </div>
      </div>

      <AsyncBoundary
        loading={loading}
        error={error}
        empty={data?.empty ?? false}
        emptyTitle='Todavía no hay datos cargados'
        emptyDetail={
          'La base de datos está vacía: no se ha ejecutado ninguna importación. ' +
          'Ejecute scripts/ingest_master_files.py para cargar los maestros Excel.'
        }
      >
        {data && (
          <>
            <section aria-label='Métricas del sistema' className='dashboard-metrics'>
              <div className='metrics'>
                {data.metrics.map((metric, index) => (
                  <article key={metric.key} className='metric'>
                    <span className='metric__icon' aria-hidden='true'>
                      {['✓', '▤', '◉', '↺'][index % 4]}
                    </span>
                    <p className='metric__value'>{metric.value.toLocaleString('es-ES')}</p>
                    <p className='metric__label'>{metric.label}</p>
                  </article>
                ))}
              </div>
            </section>

            <section aria-label='Estado de fuentes y proceso' className='panel dashboard-pipeline'>
              <div className='panel__head'>
                <div>
                  <p className='eyebrow'>Disponibilidad</p>
                  <h2>Fuentes y proceso</h2>
                </div>
                <span className='badge badge--disponible'>Estado actual</span>
              </div>
              <div className='table-wrap table-wrap--flat'>
                <table className='table'>
                <thead>
                  <tr>
                    <th scope='col'>Etapa</th>
                    <th scope='col'>Estado</th>
                    <th scope='col'>Detalle</th>
                  </tr>
                </thead>
                <tbody>
                  {data.pipeline.map((stage) => (
                    <tr key={stage.key}>
                      <th scope='row'>{stage.label}</th>
                      <td>
                        <span className={`badge badge--${stage.status}`}>
                          {STATUS_LABELS[stage.status] ?? stage.status}
                        </span>
                      </td>
                      <td className='muted'>{stage.detail}</td>
                    </tr>
                  ))}
                </tbody>
                </table>
              </div>
            </section>
          </>
        )}
      </AsyncBoundary>

      <details className='disclosure dashboard-scope'>
        <summary>Alcance técnico y activación pendiente</summary>
        <div className='cards'>
          <article className='card card--plain'>
            <h3>Qué funciona hoy</h3>
            <ul>
              <li>Consulta de los maestros importados con la procedencia de cada valor.</li>
              <li>Listado de fuentes, versiones documentales e importaciones ejecutadas.</li>
              <li>Revisión firmada campo a campo sobre el conjunto de demostración.</li>
              <li>Segunda revisión ciega, conciliación y exportación con barreras de seguridad.</li>
              <li>Versionado, diferencias y mantenimiento continuo de documentos CIMA.</li>
            </ul>
          </article>
          <article className='card card--plain'>
            <h3>Qué requiere activación o validación</h3>
            <ul>
              <li>Enlazar los documentos CIMA con los registros del despliegue real.</li>
              <li>Seleccionar el modelo local y validar sus umbrales con el conjunto oro.</li>
              <li>Confirmar con farmacia cualquier prefijo de riesgo adicional a L04.</li>
            </ul>
          </article>
        </div>
      </details>
    </div>
  )
}
