import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { DashboardScreen } from './DashboardScreen'

afterEach(() => vi.unstubAllGlobals())

it('permite pasar de un indicador al registro real que lo explica', async () => {
  vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string) => Promise.resolve(new Response(JSON.stringify(
    url.includes('/cases')
      ? { items: [{ id: 'real-1', label: 'OMEPRAZOL', detail: '123', kind: 'record' }], total: 1, limit: 25, offset: 0 }
      : {
        total_records: 1,
        entity_types: [{ key: 'medication', label: 'Medicamento', count: 1 }],
        sources: [{ key: 'master_excel', label: 'Maestro', count: 1 }],
        review: [{ key: 'pendiente', label: 'Pendiente', count: 1 }],
        coverage: [{ key: 'master_excel:present', label: 'Maestro', count: 1 }],
        pending: 1, second_review: 0, quarantined: 0, diagnostics: 0,
      },
  )))))

  render(<DashboardScreen />)
  expect(await screen.findByText('Cobertura y calidad')).toBeInTheDocument()
  expect(screen.queryByText('Cómo trabajar con Farmalidación')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Pendiente: 1 de 1 registros. Ver casos' }))
  expect(await screen.findByRole('link', { name: 'OMEPRAZOL' })).toHaveAttribute('href', '#/fichas/real-1')
})
