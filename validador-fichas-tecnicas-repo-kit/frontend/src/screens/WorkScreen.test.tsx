import { render, screen, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { WorkScreen } from './WorkScreen'

const REVIEWER = {
  identifier: 'ana',
  display_name: 'Ana',
  assurance: 'declarada' as const,
  role: 'farmaceutico' as const,
  role_label: 'Farmacéutico',
  may_sign_pharmacist_states: true,
}

const QUEUED = { target_record_id: 'rec-1', state: 'pendiente', version: 1, assignee_id: null, priority: 0 }
const SECOND = { id: 'asg-1', field_value_id: 'fv-1', field_name: 'DESCRIPCION', target_record_id: 'rec-2', state: 'desacuerdo', version: 1, second_reviewer_id: null }

function stub(second: () => Response) {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) =>
    String(input).includes('/second-reviews') ? second() : new Response(JSON.stringify([QUEUED]))))
}

afterEach(() => vi.unstubAllGlobals())

it('reúne la cola y la segunda lectura en una página con sus cifras', async () => {
  stub(() => new Response(JSON.stringify([SECOND])))
  render(<WorkScreen reviewer={REVIEWER} />)
  expect(screen.getByRole('heading', { level: 1, name: 'Revisión' })).toBeInTheDocument()
  expect(await screen.findByText('rec-1')).toBeInTheDocument()
  const second = screen.getByRole('region', { name: 'Segunda lectura' })
  expect(await within(second).findByText(/Discrepancias por conciliar \(1\)/)).toBeInTheDocument()
  const figures = screen.getByLabelText('Resumen de la revisión')
  expect(within(figures).getByText('En cola').nextSibling).toHaveTextContent('1')
  expect(within(figures).getByText('Discrepancias').nextSibling).toHaveTextContent('1')
})

it('reduce a una línea la segunda lectura cuando el servidor la rechaza', async () => {
  stub(() => new Response(JSON.stringify({ detail: 'La segunda revisión está desactivada.' }), { status: 409 }))
  render(<WorkScreen reviewer={REVIEWER} />)
  const second = screen.getByRole('region', { name: 'Segunda lectura' })
  expect(await within(second).findByRole('status')).toHaveTextContent('La segunda revisión está desactivada.')
  expect(within(second).queryByText(/Pendientes de segunda lectura/)).not.toBeInTheDocument()
  expect(screen.getByRole('region', { name: 'Cola' })).toBeInTheDocument()
})
