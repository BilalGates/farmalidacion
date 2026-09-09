import { readFileSync } from 'node:fs'

import { describe, expect, it } from 'vitest'

const styles = readFileSync('src/styles.css', 'utf8')

describe('tipografia global', () => {
  it('aplica Basic como unica familia en toda la interfaz', () => {
    expect(styles).toContain("--font-ui: 'Basic', sans-serif")
    expect(styles).not.toMatch(/font-family:\s*(?:'Inter'|'Metamorphous'|ui-monospace|monospace)/)
  })
})
