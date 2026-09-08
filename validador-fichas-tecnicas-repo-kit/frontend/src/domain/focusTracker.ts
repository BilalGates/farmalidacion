/**
 * Captura de foco por campo para la medición de tiempos (DEV-508).
 *
 * Mide en el navegador porque es donde ocurre el trabajo: deducir el tiempo de
 * la separación entre peticiones contaría como revisión una pestaña abierta y
 * olvidada.
 *
 * El descuento de inactividad NO se aplica aquí. Lo aplica `time_measurement`
 * en el backend, en un único sitio. Este módulo declara tramos observados; si
 * además los recortase, el mismo criterio viviría en dos lugares y podría
 * relajarse en uno sin que el otro se entere.
 *
 * Sí se cierra el tramo cuando la pestaña deja de estar visible: es una señal
 * observable de que el revisor dejó de trabajar, y no registrarla obligaría al
 * backend a descontar a ciegas lo que aquí se sabe con certeza.
 */

export interface FocusSpan {
  readonly fieldName: string
  readonly startedAt: number
  readonly endedAt: number
}

/** Tramos por debajo de este umbral son ruido de tabulación, no trabajo. */
const MIN_SPAN_SECONDS = 0.5

export class FocusTracker {
  private current: { fieldName: string; startedAt: number } | null = null

  constructor(private readonly emit: (span: FocusSpan) => void) {}

  /** Momento actual en segundos. Aislado para poder probarlo. */
  private now(): number {
    return Date.now() / 1000
  }

  /**
   * Declara que el foco pasó a un campo. Cierra el tramo anterior.
   *
   * Entrar dos veces en el mismo campo sin salir no reinicia el tramo: sería
   * contar dos veces el mismo trabajo.
   */
  enter(fieldName: string): void {
    if (this.current?.fieldName === fieldName) return
    this.leave()
    this.current = { fieldName, startedAt: this.now() }
  }

  /** Cierra el tramo abierto, si lo hay, y lo emite si es significativo. */
  leave(): void {
    if (this.current === null) return
    const endedAt = this.now()
    const { fieldName, startedAt } = this.current
    this.current = null
    if (endedAt - startedAt < MIN_SPAN_SECONDS) return
    this.emit({ fieldName, startedAt, endedAt })
  }

  /** Hay un tramo en curso. Útil para las pruebas y para depurar. */
  get isTracking(): boolean {
    return this.current !== null
  }
}
