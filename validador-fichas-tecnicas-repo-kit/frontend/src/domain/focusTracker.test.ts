import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { FocusTracker, type FocusSpan } from './focusTracker'

describe('captura de foco por campo', () => {
  let spans: FocusSpan[]
  let tracker: FocusTracker

  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-09-08T10:00:00Z'))
    spans = []
    tracker = new FocusTracker((span) => spans.push(span))
  })

  afterEach(() => vi.useRealTimers())

  it('emite un tramo al pasar de un campo a otro', () => {
    tracker.enter('DESCRIPCION')
    vi.advanceTimersByTime(12_000)
    tracker.enter('ACTIVO')

    expect(spans).toHaveLength(1)
    expect(spans[0].fieldName).toBe('DESCRIPCION')
    expect(spans[0].endedAt - spans[0].startedAt).toBeCloseTo(12, 3)
  })

  it('no reinicia el tramo al volver a entrar en el mismo campo', () => {
    tracker.enter('DESCRIPCION')
    vi.advanceTimersByTime(5_000)
    tracker.enter('DESCRIPCION')
    vi.advanceTimersByTime(5_000)
    tracker.leave()

    // Un único tramo de 10 s, no dos de 5: contar dos veces el mismo trabajo
    // inflaría la cifra sobre la que se calculará el ahorro.
    expect(spans).toHaveLength(1)
    expect(spans[0].endedAt - spans[0].startedAt).toBeCloseTo(10, 3)
  })

  it('descarta el roce de tabulación', () => {
    tracker.enter('DESCRIPCION')
    vi.advanceTimersByTime(100)
    tracker.enter('ACTIVO')

    expect(spans).toHaveLength(0)
  })

  it('no emite nada si nunca se entró en un campo', () => {
    tracker.leave()
    expect(spans).toHaveLength(0)
    expect(tracker.isTracking).toBe(false)
  })

  it('no recorta la inactividad: eso lo decide el backend', () => {
    tracker.enter('DESCRIPCION')
    // Ocho horas con la pestaña abierta.
    vi.advanceTimersByTime(8 * 60 * 60 * 1000)
    tracker.leave()

    // El tramo se declara entero. `time_measurement` aplica el descuento en un
    // único sitio; recortarlo aquí duplicaría el criterio.
    expect(spans[0].endedAt - spans[0].startedAt).toBeCloseTo(28_800, 3)
  })
})
