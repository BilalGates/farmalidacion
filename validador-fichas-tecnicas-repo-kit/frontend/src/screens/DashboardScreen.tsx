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
          <p className='eyebrow'>Farmalidación</p>
          <h1>Estado del sistema</h1>
          <p className='lede'>
            Cifras obtenidas de la base de datos en el momento de la consulta. Reflejan lo que
            está realmente almacenado, no una previsión.
          </p>
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
            <section aria-label='Métricas del sistema'>
              <div className='metrics'>
                {data.metrics.map((metric) => (
                  <article key={metric.key} className='metric'>
                    <p className='metric__value'>{metric.value.toLocaleString('es-ES')}</p>
                    <p className='metric__label'>{metric.label}</p>
                  </article>
                ))}
              </div>
              <p className='muted'>
                Última importación registrada:{' '}
                {data.last_import_at ? formatDateTime(data.last_import_at) : 'ninguna'}
              </p>
            </section>

            <section aria-label='Estado de fuentes y proceso'>
              <h2>Fuentes y proceso</h2>
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
            </section>
          </>
        )}
      </AsyncBoundary>

      <details className='disclosure'>
        <summary>Qué funciona hoy y qué llegará después</summary>
        <div className='cards'>
          <article className='card card--plain'>
            <h3>Qué funciona hoy</h3>
            <ul>
              <li>Consulta de los maestros importados con la procedencia de cada valor.</li>
              <li>Listado de fuentes, versiones documentales e importaciones ejecutadas.</li>
              <li>Revisión firmada campo a campo sobre el conjunto de demostración.</li>
            </ul>
          </article>
          <article className='card card--plain'>
            <h3>Qué llegará después</h3>
            <ul>
              <li>Contraste versionado con CIMA y vinculación con el maestro.</li>
              <li>Extracción asistida con evidencia literal verificable.</li>
              <li>Doble validación y exportación al sistema destino.</li>
            </ul>
          </article>
        </div>
      </details>
    </div>
  )
}
