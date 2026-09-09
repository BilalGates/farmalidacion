import { readFileSync } from 'node:fs'

import { describe, expect, it } from 'vitest'

const styles = readFileSync('src/styles.css', 'utf8')

describe('tipografia global', () => {
  it('aplica Basic como unica familia en toda la interfaz', () => {
    expect(styles).toContain("--font-ui: 'Basic', sans-serif")
    expect(styles).not.toMatch(/font-family:\s*(?:'Inter'|'Metamorphous'|ui-monospace|monospace)/)
  })
})

describe('sistema visual profesional', () => {
  it('reserva el degradado rosa-morado para el acento principal', () => {
    expect(styles).toContain('--accent-gradient: linear-gradient(118deg, #d83f86 0%, #7552df 100%)')
    expect(styles).toContain('background: var(--accent-gradient)')
  })

  it('usa radios contenidos y respeta la reduccion de movimiento', () => {
    expect(styles).toContain('--radius: 7px')
    expect(styles).toContain('@media (prefers-reduced-motion: reduce)')
    expect(styles).toContain('@keyframes screen-enter')
  })
})
