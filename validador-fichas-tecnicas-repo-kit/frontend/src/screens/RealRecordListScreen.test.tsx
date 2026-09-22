import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { RealRecordListScreen } from './RealRecordListScreen'

afterEach(() => vi.unstubAllGlobals())

const PAGE = {
  items: [],
  total: 0,
  limit: 50,
  offset: 0,
}

it('separa presentaciones, medicamentos y principios activos', async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(PAGE)))
  vi.stubGlobal('fetch', fetchMock)
  render(<RealRecordListScreen />)
  await screen.findByText('No hay registros de este origen')

  fireEvent.click(screen.getByRole('button', { name: 'Presentaciones' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
  expect(fetchMock.mock.calls[1][0]).toContain('entity_type=specialty')

  fireEvent.click(screen.getByRole('button', { name: 'Medicamentos' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
  expect(fetchMock.mock.calls[2][0]).toContain('entity_type=medication')

  fireEvent.click(screen.getByRole('button', { name: 'Principios activos' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4))
  expect(fetchMock.mock.calls[3][0]).toContain('entity_type=active_ingredient')
})

it('combina nivel y búsqueda sin descargar el catálogo al navegador', async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(PAGE)))
  vi.stubGlobal('fetch', fetchMock)
  render(<RealRecordListScreen />)
  await screen.findByText('No hay registros de este origen')

  fireEvent.click(screen.getByRole('button', { name: 'Presentaciones' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
  fireEvent.change(screen.getByRole('searchbox'), { target: { value: '654789' } })
  fireEvent.click(screen.getByRole('button', { name: 'Buscar' }))

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
  expect(fetchMock.mock.calls[2][0]).toContain('entity_type=specialty')
  expect(fetchMock.mock.calls[2][0]).toContain('q=654789')
})

