import type { DatabaseInfo } from '../api/types'

/**
 * Distintivo permanente del conjunto de datos que se está mirando.
 *
 * Es la pieza que faltaba cuando el backend servía la demo con el código nuevo
 * ya desplegado: nada en pantalla decía qué base había detrás. Aquí se declara
 * siempre, en modo REAL y en modo DEMO, porque un aviso que sólo aparece en un
 * caso se lee como decoración y deja de mirarse.
 *
 * El recuento no está escrito en la interfaz: llega de `/database-info` y es el
 * que tiene la base en ese momento.
 */
export function ModeBanner({ info }: { info: DatabaseInfo | null }) {
  if (!info) return null

  if (info.mode === 'real') {
    // Un arranque REAL sobre una base sin importar no se disimula: se nombra el
    // comando que lo resuelve, porque es exactamente la avería que ocurrió.
    if (!info.consistent) {
      return (
        <p className='mode-banner mode-banner--warning' role='status'>
          <strong>Modo REAL sin datos importados.</strong> La base «{info.database}» está
          migrada pero no contiene ningún registro real. Ejecute{' '}
          <code>python -m pharma_validator_api.cli.ingest_real_data</code> para cargar los
          maestros.
        </p>
      )
    }
    return (
      <p className='mode-banner mode-banner--real' role='status'>
        <strong>Datos reales · maestros importados.</strong>{' '}
        {info.records_real.toLocaleString('es-ES')} registros en la base «{info.database}»
        {info.import_batches > 0 && <> · {info.import_batches} lotes de importación</>}.
      </p>
    )
  }

  return (
    <p className='mode-banner mode-banner--demo' role='status'>
      <strong>Datos de demostración.</strong> Los valores de la base «{info.database}» no
      provienen de los maestros ni de CIMA y no deben usarse como evidencia clínica.
    </p>
  )
}
