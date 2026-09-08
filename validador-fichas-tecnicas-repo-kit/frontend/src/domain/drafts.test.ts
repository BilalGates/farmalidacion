import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { clearDraft, countDrafts, isEmptyDraft, readDraft, saveDraft } from './drafts'

describe('borradores de revisión no confirmados', () => {
  beforeEach(() => window.localStorage.clear())
  afterEach(() => vi.restoreAllMocks())

  it('conserva lo escrito para que recargar no repita el trabajo', () => {
    saveDraft('rec-1', 'value-1', { state: 'corregido', finalValue: '20 mg', comment: 'ajuste' })
    expect(readDraft('rec-1', 'value-1')).toMatchObject({
      state: 'corregido',
      finalValue: '20 mg',
      comment: 'ajuste',
    })
  })

  it('separa los borradores por ficha y por campo', () => {
    saveDraft('rec-1', 'value-1', { state: 'confirmado', finalValue: 'a', comment: '' })
    saveDraft('rec-2', 'value-1', { state: 'no_consta', finalValue: '', comment: '' })
    expect(readDraft('rec-1', 'value-1')?.state).toBe('confirmado')
    expect(readDraft('rec-2', 'value-1')?.state).toBe('no_consta')
    expect(readDraft('rec-1', 'value-2')).toBeNull()
  })

  it('no guarda un borrador vacío y retira el anterior', () => {
    saveDraft('rec-1', 'value-1', { state: 'confirmado', finalValue: 'a', comment: '' })
    saveDraft('rec-1', 'value-1', { state: '', finalValue: '  ', comment: '' })
    expect(readDraft('rec-1', 'value-1')).toBeNull()
    expect(isEmptyDraft({ state: '', finalValue: '', comment: '' })).toBe(true)
  })

  it('descarta el borrador cuando la decisión ya está firmada', () => {
    saveDraft('rec-1', 'value-1', { state: 'confirmado', finalValue: 'a', comment: '' })
    clearDraft('rec-1', 'value-1')
    expect(readDraft('rec-1', 'value-1')).toBeNull()
  })

  it('caduca un borrador de más de un día', () => {
    saveDraft('rec-1', 'value-1', { state: 'confirmado', finalValue: 'a', comment: '' })
    const later = Date.now() + 25 * 60 * 60 * 1000
    vi.spyOn(Date, 'now').mockReturnValue(later)
    expect(readDraft('rec-1', 'value-1')).toBeNull()
  })

  it('descarta un borrador ilegible en lugar de adivinarlo', () => {
    window.localStorage.setItem('farmalidacion.draft.rec-1.value-1', 'no es json')
    expect(readDraft('rec-1', 'value-1')).toBeNull()
  })

  it('cuenta los borradores pendientes de una ficha', () => {
    saveDraft('rec-1', 'value-1', { state: 'confirmado', finalValue: 'a', comment: '' })
    saveDraft('rec-1', 'value-2', { state: 'no_consta', finalValue: '', comment: '' })
    saveDraft('rec-2', 'value-9', { state: 'confirmado', finalValue: 'z', comment: '' })
    expect(countDrafts('rec-1')).toBe(2)
    expect(countDrafts('rec-2')).toBe(1)
    expect(countDrafts('rec-3')).toBe(0)
  })

  it('sigue funcionando sin almacenamiento disponible', () => {
    // En modo privado o con la cuota agotada, `setItem` lanza. Perder el
    // borrador es tolerable; romper la pantalla de revisión no lo es.
    vi.spyOn(window.localStorage, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError')
    })
    vi.spyOn(window.localStorage, 'getItem').mockImplementation(() => {
      throw new Error('SecurityError')
    })
    expect(() =>
      saveDraft('rec-1', 'value-1', { state: 'confirmado', finalValue: 'a', comment: '' }),
    ).not.toThrow()
    expect(readDraft('rec-1', 'value-1')).toBeNull()
  })
})
