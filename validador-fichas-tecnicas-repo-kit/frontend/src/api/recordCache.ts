import { fetchRecord } from './client'
import type { TargetRecord } from './types'

/**
 * Caché de fichas para la revisión repetitiva (DEV-509).
 *
 * Revisar es pasar por muchas fichas seguidas. Precargar la siguiente hace que
 * el salto sea inmediato en lugar de esperar a la red en cada cambio.
 *
 * Reglas que evitan que una caché mienta al revisor:
 *
 * - **Se invalida al guardar.** Una decisión cambia el estado del campo; servir
 *   la versión anterior mostraría como pendiente algo ya validado. Por eso
 *   `invalidate` se llama después de cada escritura y no se confía en un TTL.
 * - **Nunca se sirve una entrada caducada.** Una ficha guardada hace mucho
 *   puede haber cambiado por otro revisor.
 * - **Una petición en vuelo se comparte.** Pedir la misma ficha dos veces
 *   seguidas no lanza dos peticiones: la segunda espera a la primera.
 *
 * La caché guarda lo que el backend devolvió, sin transformarlo. No decide
 * nada sobre el contenido clínico.
 */

interface Entry {
  readonly record: TargetRecord
  readonly storedAt: number
}

/** Pasado este tiempo la ficha se vuelve a pedir. */
const MAX_AGE_MS = 30_000

/** Más allá de esto la caché dejaría de ser una ayuda y sería memoria retenida. */
const MAX_ENTRIES = 20

const entries = new Map<string, Entry>()
const inFlight = new Map<string, Promise<TargetRecord>>()

function fresh(entry: Entry | undefined): entry is Entry {
  return entry !== undefined && Date.now() - entry.storedAt < MAX_AGE_MS
}

function store(recordId: string, record: TargetRecord): void {
  if (entries.size >= MAX_ENTRIES) {
    const oldest = entries.keys().next().value
    if (oldest !== undefined) entries.delete(oldest)
  }
  entries.set(recordId, { record, storedAt: Date.now() })
}

/** La ficha ya cargada, si sigue siendo válida. */
export function cachedRecord(recordId: string): TargetRecord | null {
  const entry = entries.get(recordId)
  return fresh(entry) ? entry.record : null
}

/**
 * Pide la ficha, reutilizando la caché y compartiendo la petición en vuelo.
 */
export function loadRecord(recordId: string): Promise<TargetRecord> {
  const cached = cachedRecord(recordId)
  if (cached !== null) return Promise.resolve(cached)

  const pending = inFlight.get(recordId)
  if (pending !== undefined) return pending

  const request = fetchRecord(recordId)
    .then((record) => {
      store(recordId, record)
      return record
    })
    .finally(() => {
      inFlight.delete(recordId)
    })
  inFlight.set(recordId, request)
  return request
}

/**
 * Precarga una ficha sin bloquear ni propagar su error.
 *
 * Que falle la precarga no puede molestar al revisor: cuando abra esa ficha,
 * la carga normal volverá a intentarlo y mostrará el error si persiste.
 */
export function prefetchRecord(recordId: string): void {
  if (cachedRecord(recordId) !== null || inFlight.has(recordId)) return
  void loadRecord(recordId).catch(() => undefined)
}

/** Retira una ficha de la caché. Obligatorio tras escribir sobre ella. */
export function invalidateRecord(recordId: string): void {
  entries.delete(recordId)
}

/** Vacía la caché. Para las pruebas y para un cambio de revisor. */
export function clearRecordCache(): void {
  entries.clear()
  inFlight.clear()
}
