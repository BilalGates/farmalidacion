import { fetchDashboard } from '../api/client'
import { useQuery } from '../api/useQuery'
import { AsyncBoundary } from '../components/AsyncState'

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

          </>
        )}
      </AsyncBoundary>

      <section className='panel dashboard-guide' aria-labelledby='manual-title'>
        <div className='panel__head'>
          <div>
            <p className='eyebrow'>Guía de uso</p>
            <h2 id='manual-title'>Cómo trabajar con Farmalidación</h2>
          </div>
          <span className='badge badge--disponible'>Primeros pasos</span>
        </div>

        <p className='lede'>
          Farmalidación reúne los datos de los maestros, CIMA y las fichas técnicas para
          que el equipo farmacéutico pueda contrastarlos, validarlos y exportarlos con
          procedencia e historial verificables.
        </p>

        <div className='cards dashboard-guide__steps'>
          <article className='card card--plain'>
            <h3>1. Identifíquese</h3>
            <p>
              Elija su nombre en <strong>Revisor</strong>, en la cabecera. Puede consultar
              sin identificarse, pero necesita un revisor para asignarse trabajo, firmar
              decisiones, editar bloques y exportar.
            </p>
          </article>
          <article className='card card--plain'>
            <h3>2. Prepare el trabajo</h3>
            <p>
              Abra <strong>Cola de revisión</strong>, filtre los registros y asígnese un
              lote. También puede localizar directamente una ficha desde
              <strong> Registros</strong> por descripción o identificador.
            </p>
          </article>
          <article className='card card--plain'>
            <h3>3. Revise con evidencia</h3>
            <p>
              Abra un registro, seleccione un campo y contraste el valor con la evidencia
              mostrada. Registre una decisión y su valor final o comentario cuando sea
              obligatorio.
            </p>
          </article>
          <article className='card card--plain'>
            <h3>4. Complete el circuito</h3>
            <p>
              Resuelva las segundas lecturas en <strong>Validaciones</strong> y revise las
              exclusiones antes de descargar una exportación. Las discrepancias abiertas
              nunca se resuelven ni se exportan automáticamente.
            </p>
          </article>
        </div>

        <details className='disclosure dashboard-guide__detail'>
          <summary>Qué significa cada decisión</summary>
          <div className='cards'>
            <article className='card card--plain'>
              <h3>Validado o corregido</h3>
              <p>
                Confirma el valor revisado o registra uno distinto. Ambos estados exigen
                escribir el valor final; la aplicación nunca lo decide por usted.
              </p>
            </article>
            <article className='card card--plain'>
              <h3>No consta o no aplica</h3>
              <p>
                «No consta» indica que el dato no aparece tras revisar las fuentes. «No
                aplica» indica que el campo no corresponde al caso y siempre exige una
                justificación.
              </p>
            </article>
            <article className='card card--plain'>
              <h3>Requiere revisión</h3>
              <p>
                Mantiene el campo abierto cuando hace falta más análisis. Una nueva
                decisión se añade al historial y nunca borra la anterior.
              </p>
            </article>
          </div>
        </details>

        <details className='disclosure dashboard-guide__detail'>
          <summary>Funciones principales de cada apartado</summary>
          <ul>
            <li><strong>Registros:</strong> buscar fichas y revisar campos, bloques, procedencia e historial.</li>
            <li><strong>Cola de revisión:</strong> organizar, filtrar y asignar el trabajo del equipo.</li>
            <li><strong>Validaciones:</strong> realizar la segunda lectura a ciegas y conciliar discrepancias.</li>
            <li><strong>Importaciones y Fuentes:</strong> comprobar lotes, versiones, hashes e incidencias.</li>
            <li><strong>Exportaciones:</strong> generar ficheros técnicos y consultar las fichas excluidas.</li>
            <li><strong>Novedades CIMA:</strong> ver cambios documentales y campos reabiertos.</li>
            <li><strong>Revisores:</strong> gestionar las identidades y roles que pueden firmar.</li>
          </ul>
        </details>

        <p className='note'>
          <strong>Importante:</strong> la herramienta no procesa datos de pacientes, no
          prescribe ni recomienda tratamientos y no sustituye el criterio farmacéutico.
          En el piloto, la identidad seleccionada es una firma declarada, no una
          autenticación. Los datos marcados como DEMO no son evidencia clínica.
        </p>
      </section>

      {data && !data.empty && (
        <details className='disclosure dashboard-scope'>
          <summary>Fuentes y proceso</summary>
          <section aria-label='Estado de fuentes y proceso' className='dashboard-pipeline'>
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
        </details>
      )}
    </div>
  )
}
