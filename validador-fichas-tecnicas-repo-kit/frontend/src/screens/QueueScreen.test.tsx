import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { QueueScreen } from './QueueScreen'

afterEach(() => vi.unstubAllGlobals())

it('envía la versión observada al iniciar revisión y refleja el resultado', async () => {
  const item = { target_record_id: 'rec-1', state: 'asignado', version: 7, assignee_id: 'ana', priority: 0 }
  const updated = { ...item, state: 'en_revision', version: 8 }
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(new Response(JSON.stringify([item])))
    .mockResolvedValueOnce(new Response(JSON.stringify(updated)))
    .mockResolvedValueOnce(new Response(JSON.stringify([updated])))
  vi.stubGlobal('fetch', fetchMock)
  render(<QueueScreen reviewer={{ identifier: 'ana', display_name: 'Ana', assurance: 'declarada' }} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Iniciar revisión' }))
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Iniciar revisión' })).not.toBeInTheDocument())
  expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({
    reviewer_id: 'ana', state: 'en_revision', expected_version: 7,
  })
  expect(screen.getByRole('button', { name: 'Devolver a pendientes' })).toBeEnabled()
})

it('no ofrece transiciones sobre la asignación de otra persona', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify([
    { target_record_id: 'rec-1', state: 'asignado', version: 1, assignee_id: 'luis', priority: 0 },
  ]))))
  render(<QueueScreen reviewer={{ identifier: 'ana', display_name: 'Ana', assurance: 'declarada' }} />)
  await screen.findByRole('button', { name: 'Asignarme' })
  expect(screen.queryByRole('button', { name: 'Iniciar revisión' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Devolver a pendientes' })).not.toBeInTheDocument()
})

it('permite asignarse y muestra conflictos del servidor', async () => {
  const fetchMock = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify([
    { target_record_id: 'rec-1', state: 'pendiente', version: 1, assignee_id: null, priority: 0 },
  ]))).mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'Ya está asignado.' }), { status: 409 }))
  vi.stubGlobal('fetch', fetchMock)
  render(<QueueScreen reviewer={{ identifier: 'ana', display_name: 'Ana', assurance: 'declarada' }} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Asignarme' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Ya está asignado.')
  expect(fetchMock.mock.calls[1][0]).toContain('/queue/rec-1/assign')
  expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ reviewer_id: 'ana' })
})

it('no permite asignar sin revisor', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify([
    { target_record_id: 'rec-1', state: 'pendiente', version: 1, assignee_id: null, priority: 0 },
  ]))))
  render(<QueueScreen reviewer={null} />)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Asignarme' })).toBeDisabled())
})
