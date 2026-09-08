import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { QueueScreen } from './QueueScreen'

afterEach(() => vi.unstubAllGlobals())

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
