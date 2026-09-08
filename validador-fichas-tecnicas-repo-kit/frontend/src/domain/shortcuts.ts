/**
 * Mapa de atajos de la pantalla de revisión (DEV-504).
 *
 * Se declara como dato y no como una cadena de `if` dentro del componente: así
 * la tabla que se enseña al revisor y el comportamiento real salen de la misma
 * fuente, y no pueden divergir cuando se añada un atajo.
 *
 * Reglas que este mapa respeta:
 *
 * - No se usan atajos de una sola tecla sin modificador mientras el foco está
 *   en un campo de texto: escribir «c» en un comentario no puede confirmar.
 * - No se pisan atajos del navegador que el revisor necesita (Ctrl+T, Ctrl+W,
 *   Ctrl+L, F5). Se usa Alt como modificador principal, que en la práctica
 *   queda libre, y Ctrl+Enter para guardar por ser convención establecida.
 * - Ninguna acción destructiva es inmediata. `descartar` sólo abre la edición
 *   con esa decisión preseleccionada; confirmarla sigue exigiendo un acto
 *   explícito, porque un atajo no puede firmar por un farmacéutico.
 */

export type ShortcutAction =
  | 'campo_siguiente'
  | 'campo_anterior'
  | 'ficha_siguiente'
  | 'ficha_anterior'
  | 'editar'
  | 'guardar'
  | 'cancelar'
  | 'ir_a_evidencia'
  | 'volver_al_campo'
  | 'ayuda'

export interface Shortcut {
  readonly action: ShortcutAction
  /** `event.key` tal cual lo entrega el navegador. */
  readonly key: string
  readonly alt?: boolean
  readonly ctrl?: boolean
  readonly shift?: boolean
  /** Etiqueta que se muestra al revisor. */
  readonly label: string
  readonly description: string
  /**
   * Si el atajo sigue activo mientras se escribe en un campo de texto.
   * Sólo lo están los que llevan modificador y no compiten con la escritura.
   */
  readonly worksWhileTyping: boolean
}

export const SHORTCUTS: readonly Shortcut[] = [
  {
    action: 'campo_siguiente',
    key: 'ArrowDown',
    alt: true,
    label: 'Alt + ↓',
    description: 'Campo siguiente',
    worksWhileTyping: true,
  },
  {
    action: 'campo_anterior',
    key: 'ArrowUp',
    alt: true,
    label: 'Alt + ↑',
    description: 'Campo anterior',
    worksWhileTyping: true,
  },
  {
    action: 'ficha_siguiente',
    key: 'ArrowRight',
    alt: true,
    label: 'Alt + →',
    description: 'Ficha siguiente de la cola',
    worksWhileTyping: false,
  },
  {
    action: 'ficha_anterior',
    key: 'ArrowLeft',
    alt: true,
    label: 'Alt + ←',
    description: 'Ficha anterior de la cola',
    worksWhileTyping: false,
  },
  {
    action: 'editar',
    key: 'Enter',
    alt: true,
    label: 'Alt + Enter',
    description: 'Abrir o cerrar la revisión del campo activo',
    worksWhileTyping: true,
  },
  {
    action: 'guardar',
    key: 'Enter',
    ctrl: true,
    label: 'Ctrl + Enter',
    description: 'Guardar la decisión del campo activo',
    worksWhileTyping: true,
  },
  {
    action: 'cancelar',
    key: 'Escape',
    label: 'Esc',
    description: 'Cerrar la edición sin guardar',
    worksWhileTyping: true,
  },
  {
    action: 'ir_a_evidencia',
    key: 'e',
    alt: true,
    label: 'Alt + E',
    description: 'Llevar el foco a la evidencia del campo',
    worksWhileTyping: true,
  },
  {
    action: 'volver_al_campo',
    key: 'c',
    alt: true,
    label: 'Alt + C',
    description: 'Volver al campo desde la evidencia',
    worksWhileTyping: true,
  },
  {
    action: 'ayuda',
    key: '?',
    shift: true,
    label: 'Shift + ?',
    description: 'Mostrar u ocultar esta ayuda',
    worksWhileTyping: false,
  },
]

/** Estado del teclado que basta para resolver un atajo. */
export interface KeyChord {
  readonly key: string
  readonly altKey: boolean
  readonly ctrlKey: boolean
  readonly metaKey: boolean
  readonly shiftKey: boolean
}

function matches(shortcut: Shortcut, chord: KeyChord): boolean {
  if (shortcut.key.length === 1) {
    if (shortcut.key.toLowerCase() !== chord.key.toLowerCase()) return false
  } else if (shortcut.key !== chord.key) {
    return false
  }
  // Un modificador no declarado debe estar ausente: si no, Ctrl+Alt+Enter
  // dispararía dos acciones a la vez.
  if (Boolean(shortcut.alt) !== chord.altKey) return false
  if (Boolean(shortcut.ctrl) !== (chord.ctrlKey || chord.metaKey)) return false
  if (shortcut.shift !== undefined && shortcut.shift !== chord.shiftKey) return false
  return true
}

/**
 * Resuelve la acción de una pulsación, o `null` si no hay ninguna.
 *
 * `typing` indica que el foco está en un control de texto. En ese caso sólo se
 * admiten los atajos declarados como seguros: el resto se dejan pasar para que
 * el revisor pueda escribir con normalidad.
 */
export function resolveShortcut(chord: KeyChord, typing: boolean): ShortcutAction | null {
  for (const shortcut of SHORTCUTS) {
    if (!matches(shortcut, chord)) continue
    if (typing && !shortcut.worksWhileTyping) return null
    return shortcut.action
  }
  return null
}

/** Un elemento en el que el revisor está escribiendo. */
export function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  if (target.isContentEditable) return true
  const tag = target.tagName
  if (tag === 'TEXTAREA') return true
  if (tag === 'SELECT') return true
  if (tag !== 'INPUT') return false
  const type = (target as HTMLInputElement).type
  // Los botones con forma de input no capturan escritura.
  return !['button', 'submit', 'reset', 'checkbox', 'radio'].includes(type)
}
