import { describe, expect, it } from 'vitest'

import { SHORTCUTS, resolveShortcut, type KeyChord } from './shortcuts'

function chord(key: string, modifiers: Partial<KeyChord> = {}): KeyChord {
  return {
    key,
    altKey: false,
    ctrlKey: false,
    metaKey: false,
    shiftKey: false,
    ...modifiers,
  }
}

describe('mapa de atajos de revisión', () => {
  it('resuelve la navegación entre campos y fichas', () => {
    expect(resolveShortcut(chord('ArrowDown', { altKey: true }), false)).toBe('campo_siguiente')
    expect(resolveShortcut(chord('ArrowUp', { altKey: true }), false)).toBe('campo_anterior')
    expect(resolveShortcut(chord('ArrowRight', { altKey: true }), false)).toBe('ficha_siguiente')
    expect(resolveShortcut(chord('ArrowLeft', { altKey: true }), false)).toBe('ficha_anterior')
  })

  it('exige el modificador declarado y ninguno más', () => {
    // Sin Alt no es el atajo de navegación: es una flecha normal.
    expect(resolveShortcut(chord('ArrowDown'), false)).toBeNull()
    // Con un modificador de más tampoco: si no, Ctrl+Alt+Enter dispararía dos.
    expect(resolveShortcut(chord('Enter', { altKey: true, ctrlKey: true }), false)).toBeNull()
  })

  it('distingue guardar de editar por el modificador', () => {
    expect(resolveShortcut(chord('Enter', { ctrlKey: true }), false)).toBe('guardar')
    expect(resolveShortcut(chord('Enter', { altKey: true }), false)).toBe('editar')
    // Enter a secas queda para el control que tenga el foco.
    expect(resolveShortcut(chord('Enter'), false)).toBeNull()
  })

  it('acepta Meta como equivalente de Ctrl para guardar', () => {
    expect(resolveShortcut(chord('Enter', { metaKey: true }), false)).toBe('guardar')
  })

  it('no interrumpe la escritura con atajos de una sola tecla', () => {
    // Escribir «?» en un comentario no puede abrir la ayuda.
    expect(resolveShortcut(chord('?', { shiftKey: true }), true)).toBeNull()
    expect(resolveShortcut(chord('?', { shiftKey: true }), false)).toBe('ayuda')
  })

  it('mantiene activos mientras se escribe los atajos con modificador', () => {
    expect(resolveShortcut(chord('ArrowDown', { altKey: true }), true)).toBe('campo_siguiente')
    expect(resolveShortcut(chord('Enter', { ctrlKey: true }), true)).toBe('guardar')
    // Escape cierra la edición aunque el foco esté en el comentario.
    expect(resolveShortcut(chord('Escape'), true)).toBe('cancelar')
  })

  it('resuelve las letras sin depender de mayúsculas', () => {
    expect(resolveShortcut(chord('E', { altKey: true }), false)).toBe('ir_a_evidencia')
    expect(resolveShortcut(chord('e', { altKey: true }), false)).toBe('ir_a_evidencia')
  })

  it('no declara dos atajos para la misma combinación', () => {
    const seen = new Set<string>()
    for (const shortcut of SHORTCUTS) {
      const signature = [
        shortcut.key.toLowerCase(),
        shortcut.alt ? 'alt' : '',
        shortcut.ctrl ? 'ctrl' : '',
        shortcut.shift ? 'shift' : '',
      ].join('|')
      expect(seen.has(signature)).toBe(false)
      seen.add(signature)
    }
  })

  it('no reserva combinaciones que el navegador necesita', () => {
    // Ctrl+T, Ctrl+W, Ctrl+L y F5 deben seguir llegando al navegador.
    for (const key of ['t', 'w', 'l']) {
      expect(resolveShortcut(chord(key, { ctrlKey: true }), false)).toBeNull()
    }
    expect(resolveShortcut(chord('F5'), false)).toBeNull()
  })

  it('no expone ninguna acción destructiva inmediata', () => {
    // El mapa no contiene «descartar» ni «eliminar»: una tecla no puede firmar
    // ni borrar por un farmacéutico.
    const actions = SHORTCUTS.map((item) => item.action)
    expect(actions).not.toContain('descartar')
    expect(actions).not.toContain('eliminar')
  })
})
