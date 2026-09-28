import { readFileSync } from 'node:fs'

import { describe, expect, it } from 'vitest'

const styles = readFileSync('src/styles.css', 'utf8')

describe('tipografia global', () => {
  it('usa tipografia del sistema y evita fabricar grosores borrosos', () => {
    expect(styles).toContain("--font-ui: 'Segoe UI Variable', 'Segoe UI', Inter, system-ui, sans-serif")
    expect(styles).toContain('font-synthesis: none')
    expect(styles).not.toContain("--font-ui: 'Basic', sans-serif")
  })
})

describe('sistema visual profesional', () => {
  it('conserva el degradado como detalle y usa color solido en los controles', () => {
    expect(styles).toContain('--accent-gradient: linear-gradient(118deg, #d83f86 0%, #7552df 100%)')
    expect(styles).toContain('.button--primary { border-color: transparent; color: #fff; background: #7045b9;')
    expect(styles).toContain('.chip--active { border-color: #e9d6e8; color: #743d82; background: #f7edf6;')
  })

  it('usa controles redondeados y respeta la reduccion de movimiento', () => {
    expect(styles).toContain('--radius: 14px')
    expect(styles).toContain('.filter-workspace { display: grid; grid-template-columns: minmax(225px, 250px) minmax(0, 1fr)')
    expect(styles).toContain('@media (prefers-reduced-motion: reduce)')
    expect(styles).toContain('@keyframes screen-enter')
  })
})
