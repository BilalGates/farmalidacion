import type { DatabaseInfo } from '../api/types'

/**
 * Aviso de que la base servida no sirve para trabajar.
 *
 * Antes anunciaba también los casos normales —«datos reales, N registros, N
 * lotes»— en una franja permanente. Eso es ruido: quien abre la aplicación ya
 * sabe qué base pidió, y el distintivo REAL/DEMO de la barra superior lo
 * recuerda sin ocupar una línea. Un aviso que aparece siempre se lee como
 * decoración y deja de mirarse, que es justo lo que no puede pasar con éste.
 *
 * Queda sólo la avería real: modo REAL sobre una base migrada pero vacía. Esa
 * ocurrió, y sin el aviso nada en pantalla explicaba por qué no había registros.
 */
export function ModeBanner({ info }: { info: DatabaseInfo | null }) {
  if (!info || info.mode !== 'real' || info.consistent) return null

  // Se nombra el comando que lo resuelve: el aviso sin la salida es media avería.
  return (
    <p className='mode-banner mode-banner--warning' role='status'>
      <strong>Modo REAL sin datos importados.</strong> La base «{info.database}» está migrada
      pero no contiene ningún registro real. Ejecute{' '}
      <code>python -m pharma_validator_api.cli.ingest_real_data</code> para cargar los maestros.
    </p>
  )
}
