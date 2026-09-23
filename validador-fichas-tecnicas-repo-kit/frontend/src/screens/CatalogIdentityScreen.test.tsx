import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import type { Reviewer } from '../api/types'
import { CatalogIdentityScreen } from './CatalogIdentityScreen'

afterEach(() => vi.unstubAllGlobals())

const IDENTITY = {
  id: 'dcp-1', identity_type: 'dcp', code: 'M-1', display_name: 'Medicamento ejemplo',
  target_record_id: 'record-1', source_system: 'canonical_target_record',
  source_version: 'target-record-v1', source_literal: 'M-1', active: true, version: 1,
}
const REVIEWER = { identifier: 'ana', display_name: 'Ana', assurance: 'declarada' } as Reviewer

it('exige motivo y conserva el actor al modificar', async () => {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === 'PUT') return new Response(JSON.stringify({ ...IDENTITY, display_name: 'Nombre corregido', version: 2 }))
    if (url.includes('/history')) return new Response(JSON.stringify([]))
    if (url.includes('/relations')) return new Response(JSON.stringify([]))
    if (url.includes('/classifications')) return new Response(JSON.stringify([]))
    return new Response(JSON.stringify(IDENTITY))
  })
  vi.stubGlobal('fetch', fetchMock)
  render(<CatalogIdentityScreen identityId='dcp-1' reviewer={REVIEWER} />)

  await screen.findByRole('heading', { name: 'Medicamento ejemplo' })
  const save = screen.getByRole('button', { name: 'Guardar cambios' })
  expect(save).toBeDisabled()
  fireEvent.change(screen.getByLabelText('Nombre visible'), { target: { value: 'Nombre corregido' } })
  fireEvent.change(screen.getByLabelText('Motivo del cambio'), { target: { value: 'Corrección revisada.' } })
  fireEvent.click(save)

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(5))
  const payload = JSON.parse(String(fetchMock.mock.calls[3][1]?.body))
  expect(payload).toMatchObject({ actor_id: 'ana', expected_version: 1, reason: 'Corrección revisada.' })
})
