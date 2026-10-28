import { readFileSync } from 'node:fs'

import { describe, expect, it } from 'vitest'

const tokens = readFileSync('src/ui/tokens.css', 'utf8')
const styles = tokens + readFileSync('src/studio.css', 'utf8')
const entry = readFileSync('src/main.tsx', 'utf8')

describe('tipografia global', () => {
  it('usa tipografia del sistema y evita fabricar grosores borrosos', () => {
    expect(styles).toContain("--font-ui: 'Segoe UI Variable', 'Segoe UI', Inter, system-ui, sans-serif")
    expect(entry.indexOf("import './studio.css'")).toBeGreaterThan(entry.indexOf("import './styles.css'"))
    expect(entry.indexOf("import './ui/tokens.css'")).toBeLessThan(entry.indexOf("import './styles.css'"))
  })
})

describe('tokens', () => {
  it('se definen en un único archivo', () => {
    for (const file of ['src/styles.css', 'src/studio.css']) {
      expect(readFileSync(file, 'utf8')).not.toMatch(/^:root(\[[^\]]+\])? \{[^{}]*--[a-z-]+:/m)
    }
  })
})

describe('capa común y hojas migradas', () => {
  // El código nuevo sólo usa tokens: un color o un tamaño escrito a mano es
  // exactamente la deriva que llevó a cinco paletas superpuestas.
  const migrated = ['src/ui/components.css', 'src/screens/catalog.css', 'src/screens/work.css', 'src/screens/sources.css', 'src/screens/review.css']
  it.each(migrated)('%s no escribe colores ni tamaños de letra literales', (file) => {
    const css = readFileSync(file, 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')
    expect(css).not.toMatch(/#[0-9a-f]{3,8}\b/i)
    expect(css).not.toMatch(/\brgba?\(/)
    expect(css).not.toMatch(/font-size:\s*[0-9.]+(rem|px|em)/)
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

describe('desplegables', () => {
  it('da estilo al panel de opciones y conserva un fallback nativo', () => {
    expect(styles).toContain('select option { color: var(--ink); background: var(--surface); }')
    expect(styles).toContain('@supports (appearance: base-select)')
    expect(styles).toContain('select::picker(select)')
    expect(styles).toContain('select option:disabled')
  })
})

describe('barras de desplazamiento', () => {
  it('estiliza ambos ejes y adapta el color al tema oscuro', () => {
    expect(styles).toContain('scrollbar-width: thin')
    expect(styles).toContain('scrollbar-color: var(--scrollbar-thumb) transparent')
    expect(styles).toContain('::-webkit-scrollbar { width: 10px; height: 10px; }')
    expect(styles).toContain('::-webkit-scrollbar-thumb:hover')
    expect(styles).toContain('--scrollbar-thumb: #777080')
  })
})
