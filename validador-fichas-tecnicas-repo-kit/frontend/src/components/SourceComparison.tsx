import type { FieldValue } from '../api/types'
import { sourceLabel } from '../domain/vocabulary'
import { markUniqueWords } from '../domain/wordDiff'

/** Lo que afirma una fuente sobre un campo. */
export interface SourceClaim {
  readonly key: string
  readonly source: string
  readonly text: string
}

function sourceOf(value: FieldValue): string {
  const roles = [...new Set(value.provenance.map(item => sourceLabel(item.provenance_role)))]
  return roles.join(' y ') || 'Sin fuente'
}

/**
 * Valores rivales de un campo en discrepancia, o `null` si no la hay.
 *
 * Sólo compara lo que el backend marca como discrepancia: varios valores del
 * mismo campo, uno por fuente. El `literal_text` de la procedencia es el
 * fragmento de evidencia (una celda, un párrafo de la ficha), no el valor, y
 * compararlo señalaría diferencias que no lo son.
 */
export function divergentClaims(value: FieldValue, siblings: readonly FieldValue[] = []): SourceClaim[] | null {
  if (!value.has_conflict) return null
  const claims: SourceClaim[] = siblings
    .filter(other => other.field_name === value.field_name && other.has_conflict && other.literal_value !== null)
    .map(item => ({ key: item.id, source: sourceOf(item), text: item.literal_value! }))
  const distinct = new Set(claims.map(claim => claim.text.trim().toLocaleLowerCase('es-ES')))
  return claims.length > 1 && distinct.size > 1 ? claims : null
}

/**
 * Lo que afirma cada fuente, una debajo de otra, con lo que sólo dice ella
 * resaltado. Acompaña a la decisión; no la sustituye.
 */
export function SourceComparison({ claims }: { readonly claims: readonly SourceClaim[] | null }) {
  if (!claims) return null
  return (
    <dl className='source-comparison' aria-label='Lo que dice cada fuente'>
      {claims.map((claim, index) => {
        const others = claims.filter((_, other) => other !== index).map(other => other.text)
        return (
          <div key={claim.key}>
            <dt>{claim.source}</dt>
            <dd>{markUniqueWords(claim.text, others).map((piece, at) => piece.unique
              ? <mark key={at}>{piece.text}</mark>
              : <span key={at}>{piece.text}</span>)}</dd>
          </div>
        )
      })}
    </dl>
  )
}
