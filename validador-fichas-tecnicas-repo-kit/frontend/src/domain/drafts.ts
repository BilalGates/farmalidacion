/**
 * Borradores de revisión no confirmados (DEV-505).
 *
 * Un borrador es lo que el revisor ha escrito pero **todavía no ha firmado**.
 * Se guarda en el navegador para que recargar la pestaña no le haga repetir el
 * trabajo, y en ningún caso se envía al backend por su cuenta: una decisión
 * clínica se persiste cuando el revisor la guarda, no cuando deja de teclear.
 *
 * Esa distinción es la razón de que el autoguardado de esta pantalla sea local.
 * Autoguardar contra el servidor convertiría un texto a medio escribir en una
 * decisión firmada, que es precisamente lo que la especificación 9 prohíbe.
 *
 * El almacenamiento puede fallar o estar deshabilitado (modo privado, cuota
 * agotada). Un borrador perdido es una molestia; una excepción no capturada
 * dejaría la pantalla de revisión inservible, así que todo acceso va protegido
 * y su ausencia se trata como «no hay borrador».
 */

export interface DraftDecision {
  readonly state: string
  readonly finalValue: string
  readonly comment: string
  /** Momento en que se guardó, para poder caducarlo y para informar al revisor. */
  readonly savedAt: number
}

/** Un borrador viejo describe una sesión que ya no está en curso. */
const MAX_AGE_MS = 24 * 60 * 60 * 1000

const PREFIX = 'farmalidacion.draft.'

function key(recordId: string, fieldValueId: string): string {
  return `${PREFIX}${recordId}.${fieldValueId}`
}

/** Un borrador vacío no se guarda: no hay trabajo que proteger. */
export function isEmptyDraft(draft: Omit<DraftDecision, 'savedAt'>): boolean {
  return draft.state === '' && draft.finalValue.trim() === '' && draft.comment.trim() === ''
}

export function saveDraft(
  recordId: string,
  fieldValueId: string,
  draft: Omit<DraftDecision, 'savedAt'>,
): void {
  try {
    if (isEmptyDraft(draft)) {
      window.localStorage.removeItem(key(recordId, fieldValueId))
      return
    }
    const payload: DraftDecision = { ...draft, savedAt: Date.now() }
    window.localStorage.setItem(key(recordId, fieldValueId), JSON.stringify(payload))
  } catch {
    // Sin almacenamiento se sigue revisando; sólo se pierde la recuperación.
  }
}

export function readDraft(recordId: string, fieldValueId: string): DraftDecision | null {
  try {
    const raw = window.localStorage.getItem(key(recordId, fieldValueId))
    if (raw === null) return null
    const parsed = JSON.parse(raw) as Partial<DraftDecision>
    if (typeof parsed.savedAt !== 'number') return null
    if (Date.now() - parsed.savedAt > MAX_AGE_MS) {
      window.localStorage.removeItem(key(recordId, fieldValueId))
      return null
    }
    return {
      state: typeof parsed.state === 'string' ? parsed.state : '',
      finalValue: typeof parsed.finalValue === 'string' ? parsed.finalValue : '',
      comment: typeof parsed.comment === 'string' ? parsed.comment : '',
      savedAt: parsed.savedAt,
    }
  } catch {
    // Un borrador ilegible se descarta: no se adivina lo que quiso escribir.
    return null
  }
}

/** Se descarta cuando la decisión ya está firmada en el backend. */
export function clearDraft(recordId: string, fieldValueId: string): void {
  try {
    window.localStorage.removeItem(key(recordId, fieldValueId))
  } catch {
    // Ver `saveDraft`.
  }
}

/** Borradores pendientes de una ficha, para avisar antes de abandonarla. */
export function countDrafts(recordId: string): number {
  try {
    let total = 0
    const prefix = `${PREFIX}${recordId}.`
    for (let index = 0; index < window.localStorage.length; index += 1) {
      const name = window.localStorage.key(index)
      if (name !== null && name.startsWith(prefix)) total += 1
    }
    return total
  } catch {
    return 0
  }
}
