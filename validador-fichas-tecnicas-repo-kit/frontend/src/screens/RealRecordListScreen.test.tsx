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

it('separa los niveles farmacéuticos del catálogo', async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(PAGE)))
  vi.stubGlobal('fetch', fetchMock)
  render(<RealRecordListScreen />)
  await screen.findByText('No hay identidades en este nivel')

  fireEvent.click(screen.getByRole('button', { name: 'Presentaciones' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
  expect(fetchMock.mock.calls[1][0]).toContain('identity_type=presentation')

  fireEvent.click(screen.getByRole('button', { name: 'DCP' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
  expect(fetchMock.mock.calls[2][0]).toContain('identity_type=dcp')

  fireEvent.click(screen.getByRole('button', { name: 'Sustancias activas' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4))
  expect(fetchMock.mock.calls[3][0]).toContain('identity_type=active_ingredient')
})

it('combina nivel y búsqueda sin descargar el catálogo al navegador', async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(PAGE)))
  vi.stubGlobal('fetch', fetchMock)
  render(<RealRecordListScreen />)
  await screen.findByText('No hay identidades en este nivel')

  fireEvent.click(screen.getByRole('button', { name: 'Presentaciones' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
  fireEvent.change(screen.getByRole('searchbox'), { target: { value: '654789' } })
  fireEvent.click(screen.getByRole('button', { name: 'Buscar' }))

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
  expect(fetchMock.mock.calls[2][0]).toContain('identity_type=presentation')
  expect(fetchMock.mock.calls[2][0]).toContain('q=654789')
})

it('combina clase comercial y condición como filtros del servidor', async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(PAGE)))
  vi.stubGlobal('fetch', fetchMock)
  render(<RealRecordListScreen />)
  await screen.findByText('No hay identidades en este nivel')

  fireEvent.click(screen.getByRole('button', { name: 'Presentaciones' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
  fireEvent.click(screen.getByRole('button', { name: 'Genérico' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
  fireEvent.change(screen.getByLabelText('Condición'), { target: { value: 'huerfano' } })
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4))

  expect(fetchMock.mock.calls[3][0]).toContain('commercial_class=generico')
  expect(fetchMock.mock.calls[3][0]).toContain('condition=huerfano')
})
