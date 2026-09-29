import { readFileSync } from 'node:fs'

import { describe, expect, it } from 'vitest'

const styles = readFileSync('src/design-system.css', 'utf8')
const entry = readFileSync('src/main.tsx', 'utf8')

describe('tipografia global', () => {
  it('usa tipografia del sistema y evita fabricar grosores borrosos', () => {
    expect(styles).toContain("--font-ui: 'Segoe UI Variable', 'Segoe UI', Inter, system-ui, sans-serif")
    expect(entry.indexOf("import './design-system.css'")).toBeGreaterThan(entry.indexOf("import './styles.css'"))
  })
})

describe('sistema visual profesional', () => {
  it('centraliza semántica y usa acento sólido en la acción primaria', () => {
    for (const token of ['--accent:', '--success:', '--warn:', '--danger:', '--info:', '--space-4:', '--radius:', '--text-title:', '--z-popover:']) {
      expect(styles).toContain(token)
    }
    expect(styles).toContain('.button--primary { border-color: var(--accent);')
    expect(styles).not.toContain('linear-gradient(')
  })

  it('usa radios contenidos, foco visible y respeta la reduccion de movimiento', () => {
    expect(styles).toContain('--radius: 8px')
    expect(styles).toContain(':focus-visible')
    expect(styles).toContain('@media (prefers-reduced-motion: reduce)')
  })
})
