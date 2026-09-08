import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  cachedRecord,
  clearRecordCache,
  invalidateRecord,
  loadRecord,
  prefetchRecord,
} from './recordCache'

/**
 * Caché de fichas (DEV-509).
 *
 * Lo que se comprueba es que la caché no pueda mostrar al revisor un estado
 * que ya no es el del backend: una decisión guardada tiene que invalidarla.
 */

function record(id: string) {
  return { id, entity_type: 'specialty', external_identifiers: [], blocks: [] }
}

describe('caché de fichas para revisión repetitiva', () => {
  beforeEach(() => {
    clearRecordCache()
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-09-08T10:00:00Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  function stub() {
    const mock = vi.fn(async (input: RequestInfo | URL) => {
      const id = String(input).split('/').pop() ?? ''
      return { ok: true, status: 200, json: async () => record(id) } as Response
    })
    vi.stubGlobal('fetch', mock)
    return mock
  }

  it('sirve la segunda lectura sin volver a pedirla', async () => {
    const mock = stub()
    await loadRecord('rec-1')
    await loadRecord('rec-1')
    expect(mock).toHaveBeenCalledTimes(1)
  })

  it('comparte una petición en vuelo en lugar de duplicarla', async () => {
    const mock = stub()
    await Promise.all([loadRecord('rec-1'), loadRecord('rec-1'), loadRecord('rec-1')])
    expect(mock).toHaveBeenCalledTimes(1)
  })

  it('deja de servir una entrada caducada', async () => {
    const mock = stub()
    await loadRecord('rec-1')
    vi.setSystemTime(new Date('2026-09-08T10:01:00Z'))
    // Otro revisor puede haberla cambiado: se vuelve a pedir.
    expect(cachedRecord('rec-1')).toBeNull()
    await loadRecord('rec-1')
    expect(mock).toHaveBeenCalledTimes(2)
  })

  it('se invalida al guardar, para no mostrar un estado ya superado', async () => {
    const mock = stub()
    await loadRecord('rec-1')
    invalidateRecord('rec-1')
    expect(cachedRecord('rec-1')).toBeNull()
    await loadRecord('rec-1')
    expect(mock).toHaveBeenCalledTimes(2)
  })

  it('la precarga deja la ficha lista para el salto siguiente', async () => {
    const mock = stub()
    prefetchRecord('rec-2')
    await vi.waitFor(() => expect(cachedRecord('rec-2')).not.toBeNull())
    // Abrirla después no cuesta una petición nueva.
    await loadRecord('rec-2')
    expect(mock).toHaveBeenCalledTimes(1)
  })

  it('un fallo de precarga no propaga error', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => ({ detail: 'error' }),
      } as Response),
    )
    expect(() => prefetchRecord('rec-3')).not.toThrow()
    await vi.waitFor(() => expect(cachedRecord('rec-3')).toBeNull())
  })

  it('no precarga lo que ya está en caché', async () => {
    const mock = stub()
    await loadRecord('rec-1')
    prefetchRecord('rec-1')
    expect(mock).toHaveBeenCalledTimes(1)
  })
})
