/**
 * Señala qué palabras de un literal no aparecen en los demás.
 *
 * Sirve para que el revisor vea de un vistazo en qué discrepan dos fuentes
 * («cápsula dura» frente a «cápsula dura gastrorresistente»). Es una ayuda de
 * lectura, no una comparación clínica: compara palabras sin mayúsculas, tildes
 * ni signos, y nunca decide cuál de los valores es el correcto.
 */

export interface WordPiece {
  readonly text: string
  /** La palabra no aparece en ningún otro literal. */
  readonly unique: boolean
}

function normalize(word: string): string {
  return word
    .toLocaleLowerCase('es-ES')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^\p{L}\p{N}]/gu, '')
}

function wordsOf(text: string): Set<string> {
  return new Set(text.split(/\s+/).map(normalize).filter(Boolean))
}

export function markUniqueWords(text: string, others: readonly string[]): WordPiece[] {
  const elsewhere = new Set(others.flatMap(other => [...wordsOf(other)]))
  return text.split(/(\s+)/).filter(part => part !== '').map(part => {
    const key = normalize(part)
    return { text: part, unique: key !== '' && !elsewhere.has(key) }
  })
}
