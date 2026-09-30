import { useState } from 'react'
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

/** Una celda de la fila de origen, tal y como la serializa la importación. */
type EvidenceCell = {
  column: number
  header: string | null
  literal_value: string | null
  observed_type: string | null
  formula: string | null
}

/**
 * Interpreta la fila de origen serializada, o `null` si no lo es.
 *
 * La importación guarda la fila entera y no sólo la celda del campo: el
 * contexto es lo que permite comprobar que el valor se leyó de donde dice. Pero
 * guardarla entera no obliga a mostrarla en crudo, que es lo que hacía esta
 * vista: un JSON de una línea no es evidencia legible para quien revisa.
 *
 * Un texto que no sea esa estructura se devuelve como `null` y se sigue
 * mostrando tal cual: preferimos enseñar el original a arriesgarnos a ocultar
 * una evidencia que no supimos interpretar.
 */
export function parseEvidenceRow(literalText: string): EvidenceCell[] | null {
  let parsed: unknown
  try {
    parsed = JSON.parse(literalText)
  } catch {
    return null
  }
  if (!Array.isArray(parsed) || parsed.length === 0) return null
  const cells: EvidenceCell[] = []
  for (const entry of parsed) {
    if (typeof entry !== 'object' || entry === null) return null
    const cell = entry as Record<string, unknown>
    if (!('column' in cell) || !('literal_value' in cell)) return null
    cells.push({
      column: typeof cell.column === 'number' ? cell.column : 0,
      header: typeof cell.header === 'string' ? cell.header : null,
      literal_value: typeof cell.literal_value === 'string' ? cell.literal_value : null,
      observed_type: typeof cell.observed_type === 'string' ? cell.observed_type : null,
      formula: typeof cell.formula === 'string' ? cell.formula : null,
    })
  }
  return cells
}

/**
 * La fila de origen como tabla, con la celda del campo revisado destacada.
 *
 * Destacar exige saber qué campo se revisa; sin `highlightField` la tabla se
 * muestra igual, sólo que sin resaltar. Las celdas vacías se conservan: que el
 * origen no traiga valor es en sí un dato para quien revisa, y omitirlas haría
 * indistinguible «no venía» de «no lo mostramos».
 */
function EvidenceRow({
  cells,
  highlightField,
  contextual = false,
}: {
  cells: EvidenceCell[]
  highlightField?: string
  contextual?: boolean
}) {
  const [expanded, setExpanded] = useState(false)
  const indices = cells.flatMap((cell, index) => cell.header === highlightField ? [index] : [])
  const contextCells = indices.length > 0
    ? cells.filter((_, index) => indices.some(active => Math.abs(index - active) <= 1))
    : cells
  const visibleCells = contextual && !expanded ? contextCells : cells
  return (
    <>
    <table className='evidence-row'>
      <tbody>
        {visibleCells.map((cell) => {
          const isHighlighted =
            highlightField !== undefined && cell.header !== null && cell.header === highlightField
          return (
            <tr
              key={cell.column}
              className={isHighlighted ? 'evidence-row__cell--active' : undefined}
            >
              <th scope='row'>{cell.header ?? `Columna ${cell.column}`}</th>
              <td>
                {cell.literal_value ?? <span className='muted'>sin valor</span>}
                {cell.formula !== null && (
                  <span className='evidence-row__formula'> ={cell.formula}</span>
                )}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
    {contextual && contextCells.length < cells.length && <button type='button' className='button button--ghost'
      aria-expanded={expanded} onClick={() => setExpanded(current => !current)}>
      {expanded ? 'Ver fragmento con contexto' : `Ver fila completa (${cells.length} celdas)`}
    </button>}
    </>
  )
}

/** Una procedencia. Interpreta el fragmento una sola vez y decide cómo pintarlo. */
function ProvenanceItem({
  item,
  showEvidence,
  highlightField,
  contextual,
}: {
  item: Provenance
  showEvidence: boolean
  highlightField?: string
  contextual?: boolean
}) {
  const cells = item.literal_text === null ? null : parseEvidenceRow(item.literal_text)
  return (
    <li>
      <div className='sources__summary'>
        <span className='sources__role'>{sourceLabel(item.provenance_role)}</span>
        <span className='sources__locator'>{describeLocator(item.locator, item.locator_type)}</span>
      </div>
      {showEvidence &&
        (item.literal_text ? (
          <>
            {cells === null ? (
              <blockquote className='sources__evidence'>{item.literal_text}</blockquote>
            ) : (
              <EvidenceRow cells={cells} highlightField={highlightField} contextual={contextual} />
            )}
            <details className='sources__technical'>
              <summary>Detalles técnicos de la fuente</summary>
              <dl>
                <div><dt>Versión</dt><dd>{item.document_version_id}</dd></div>
                <div><dt>Tipo de localizador</dt><dd>{item.locator_type}</dd></div>
                <div><dt>Localizador original</dt><dd>{item.locator}</dd></div>
                {/* Sólo si la tabla lo reformateó: si se mostró tal cual,
                    repetirlo aquí sería el mismo texto dos veces. */}
                {cells !== null && (
                  <div>
                    <dt>Fragmento original</dt>
                    <dd><code className='sources__raw'>{item.literal_text}</code></dd>
                  </div>
                )}
              </dl>
            </details>
          </>
        ) : (
          <span className='muted'>Esta fuente no aporta fragmento textual.</span>
        ))}
    </li>
  )
}

export function ProvenanceList({
  provenance,
  showEvidence = true,
  highlightField,
  contextual = false,
}: {
  provenance: Provenance[]
  showEvidence?: boolean
  /** Campo que se está revisando; su celda se destaca en la fila de origen. */
  highlightField?: string
  contextual?: boolean
}) {
  if (provenance.length === 0) {
    return <p className='muted'>Sin procedencia declarada.</p>
  }
  return (
    <ul className='sources'>
      {provenance.map((item) => (
        <ProvenanceItem
          key={item.source_fragment_id}
          item={item}
          showEvidence={showEvidence}
          highlightField={highlightField}
          contextual={contextual}
        />
      ))}
    </ul>
  )
}
