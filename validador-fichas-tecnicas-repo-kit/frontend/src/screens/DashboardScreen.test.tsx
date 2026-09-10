import { render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { DashboardScreen } from './DashboardScreen'

afterEach(() => vi.unstubAllGlobals())

it('muestra en Inicio la guía de uso y sus accesos principales', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
    metrics: [],
    pipeline: [],
    last_import_at: null,
    empty: false,
  }))))

  render(<DashboardScreen />)

  expect(await screen.findByRole('heading', { name: 'Cómo trabajar con Farmalidación' })).toBeInTheDocument()
  expect(screen.getByText(/no procesa datos de pacientes/i)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Ir a la cola de revisión' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Buscar un registro' })).not.toBeInTheDocument()
  expect(screen.getByText('Qué significa cada decisión')).toBeInTheDocument()
  expect(screen.getByText('Funciones principales de cada apartado')).toBeInTheDocument()
  expect(screen.getByText('Fuentes y proceso').closest('details')).not.toHaveAttribute('open')
  expect(screen.queryByText('Alcance técnico y activación pendiente')).not.toBeInTheDocument()
})
