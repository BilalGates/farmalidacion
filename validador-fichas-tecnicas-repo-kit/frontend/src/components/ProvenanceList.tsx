import type { Provenance } from '../api/types'
import { sourceLabel } from '../domain/vocabulary'

/**
 * Procedencia de un valor, en un único componente para toda la aplicación.
 *
 * Antes existían dos representaciones distintas de lo mismo: la de la vertical
 * de revisión y la de la ficha real. Dos implementaciones de la procedencia son
 * dos sitios donde puede degradarse la trazabilidad sin que nadie lo note, así
 * que la convergencia de `/fichas` sobre `/records/*` las reduce a esta.
 *
 * No inventa procedencia: un valor sin fuentes declaradas lo dice, en lugar de
 * mostrar un hueco que pueda confundirse con un dato sin comprobar.
 */

/** Traduce el localizador del fragmento sin ocultar el original. */
export function describeLocator(locator: string, locatorType: string): string {
  if (locatorType === 'excel_row') {
    try {
      const parsed = JSON.parse(locator) as { sheet?: string; row?: number }
      if (parsed.sheet && parsed.row) return `Hoja ${parsed.sheet}, fila ${parsed.row}`
    } catch {
      // Un localizador que no sea JSON se muestra tal cual.
    }
  }
  return locator
}

export function ProvenanceList({
  provenance,
  showEvidence = true,
}: {
  provenance: Provenance[]
  showEvidence?: boolean
}) {
  if (provenance.length === 0) {
    return <p className='muted'>Sin procedencia declarada.</p>
  }
  return (
    <ul className='sources'>
      {provenance.map((item) => (
        <li key={item.source_fragment_id}>
          <span className='sources__role'>{sourceLabel(item.provenance_role)}</span>
          <span className='sources__locator'>
            {describeLocator(item.locator, item.locator_type)}
          </span>
          <span className='sources__version'>Versión {item.document_version_id}</span>
          {showEvidence &&
            (item.literal_text ? (
              <blockquote className='sources__evidence'>{item.literal_text}</blockquote>
            ) : (
              <span className='muted'>Esta fuente no aporta fragmento textual.</span>
            ))}
        </li>
      ))}
    </ul>
  )
}
