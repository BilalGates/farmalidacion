import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { App } from './App'

describe('App', () => {
  it('renders the Spanish technical shell and its safety boundary', () => {
    render(<App />)

    expect(screen.getByRole('heading', { level: 1, name: 'Validador de fichas técnicas' })).toBeVisible()
    expect(screen.getByText('Este corte no toma decisiones farmacéuticas')).toBeVisible()
    expect(screen.getByText('Sin datos de pacientes')).toBeVisible()
  })
})
