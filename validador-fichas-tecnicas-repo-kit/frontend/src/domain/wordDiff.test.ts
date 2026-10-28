import { describe, expect, it } from 'vitest'

import { markUniqueWords } from './wordDiff'

const unique = (text: string, others: string[]) =>
  markUniqueWords(text, others).filter(piece => piece.unique).map(piece => piece.text)

describe('markUniqueWords', () => {
  it('marca sólo lo que falta en las demás fuentes', () => {
    expect(unique('Cápsula dura gastrorresistente', ['Cápsula dura'])).toEqual(['gastrorresistente'])
    expect(unique('Cápsula dura', ['Cápsula dura gastrorresistente'])).toEqual([])
  })

  it('ignora mayúsculas, tildes y signos', () => {
    expect(unique('CAPSULA DURA.', ['cápsula dura'])).toEqual([])
  })

  it('conserva el texto original, espacios incluidos', () => {
    expect(markUniqueWords('20  mg', ['20 mg']).map(piece => piece.text).join('')).toBe('20  mg')
  })

  it('sin otras fuentes, todo es propio', () => {
    expect(unique('L04AB04', [])).toEqual(['L04AB04'])
  })
})
