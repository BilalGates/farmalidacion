import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { ContextualChat } from './ContextualChat'

afterEach(() => vi.unstubAllGlobals())

it('muestra siempre apartado y versión junto al fragmento literal', async () => {
  const fetchMock = vi.fn(async () => ({
    ok: true,
    status: 200,
    json: async () => ({
      status: 'answered',
      message: 'Se encontró evidencia literal.',
      citations: [{ document_version_id: 'version-1', section: '6.3', literal_text: 'Texto literal.' }],
    }),
  }) as Response)
  vi.stubGlobal('fetch', fetchMock)
  render(<ContextualChat recordId='record-1' />)

  fireEvent.click(screen.getByRole('button', { name: 'Consulta documental' }))
  fireEvent.change(screen.getByLabelText('Pregunta sobre el documento'), {
    target: { value: 'Enséñame el apartado 6.3' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Buscar evidencia' }))

  expect(await screen.findByText('Texto literal.')).toBeInTheDocument()
  expect(screen.getByText(/Apartado 6.3 · versión version-1/)).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledTimes(1)
})
