import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { QueueScreen } from './QueueScreen'

const REVIEWER = {
  identifier: 'ana',
  display_name: 'Ana',
  assurance: 'declarada',
  role: 'farmaceutico' as const,
  role_label: 'Farmacéutico',
  may_sign_pharmacist_states: true,
}

afterEach(() => vi.unstubAllGlobals())

it('envía la versión observada al iniciar revisión y refleja el resultado', async () => {
  const item = { target_record_id: 'rec-1', state: 'asignado', version: 7, assignee_id: 'ana', priority: 0 }
  const updated = { ...item, state: 'en_revision', version: 8 }
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(new Response(JSON.stringify([item])))
    .mockResolvedValueOnce(new Response(JSON.stringify(updated)))
    .mockResolvedValueOnce(new Response(JSON.stringify([updated])))
  vi.stubGlobal('fetch', fetchMock)
  render(<QueueScreen reviewer={REVIEWER} />)
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
  render(<QueueScreen reviewer={REVIEWER} />)
  await screen.findByRole('button', { name: 'Asignarme' })
  expect(screen.queryByRole('button', { name: 'Iniciar revisión' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Devolver a pendientes' })).not.toBeInTheDocument()
})

it('permite asignarse y muestra conflictos del servidor', async () => {
  const fetchMock = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify([
    { target_record_id: 'rec-1', state: 'pendiente', version: 1, assignee_id: null, priority: 0 },
  ]))).mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'Ya está asignado.' }), { status: 409 }))
  vi.stubGlobal('fetch', fetchMock)
  render(<QueueScreen reviewer={REVIEWER} />)
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

it('envía los filtros explícitos al servidor', async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify([])))
  vi.stubGlobal('fetch', fetchMock)
  render(<QueueScreen reviewer={null} />)
  await screen.findByText('La cola está al día')
  fireEvent.click(screen.getByRole('button', { name: /Más filtros/ }))
  fireEvent.change(screen.getByLabelText('Entidad'), { target: { value: 'medicamento' } })
  fireEvent.change(screen.getByLabelText('Bloque'), { target: { value: 'general' } })
  fireEvent.change(screen.getByLabelText('Filtrar por conjunto'), { target: { value: 'oro' } })
  fireEvent.change(screen.getByLabelText('Filtrar doble validación'), { target: { value: 'true' } })
  fireEvent.click(screen.getByRole('button', { name: 'Aplicar filtros' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
  expect(fetchMock.mock.calls[1][0]).toContain(
    '/queue?entity_type=medicamento&block_type=general&review_set=oro&requires_second_review=true',
  )
})

it('asigna una selección como lote versionado', async () => {
  const item = {
    target_record_id: 'rec-1', state: 'pendiente', version: 4, assignee_id: null,
    priority: 0, review_set: 'corpus', requires_second_review: false,
  }
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(new Response(JSON.stringify([item])))
    .mockResolvedValueOnce(new Response(JSON.stringify([{ ...item, assignee_id: 'ana' }])))
    .mockResolvedValueOnce(new Response(JSON.stringify([{ ...item, assignee_id: 'ana' }])))
  vi.stubGlobal('fetch', fetchMock)
  render(<QueueScreen reviewer={REVIEWER} />)
  fireEvent.click(await screen.findByRole('checkbox', { name: 'Seleccionar rec-1' }))
  fireEvent.click(screen.getByRole('button', { name: 'Asignarme lote' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
  expect(fetchMock.mock.calls[1][0]).toContain('/queue/assign-batch')
  expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({
    reviewer_id: 'ana',
    items: [{ target_record_id: 'rec-1', expected_version: 4 }],
  })
})
