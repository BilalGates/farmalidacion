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
const SOURCE_RECORD = {
  id: 'record-1', entity_type: 'medication', external_identifiers: [], blocks: [{
    id: 'block-1', block_type: 'General', ordinal: 1, values: [{
      id: 'field-1', field_name: 'DESCRIPCION', source_column_index: 2,
      literal_value: 'Nombre original', maintained_value: 'Nombre original',
      maintenance_sequence: 0, maintenance_history: [], observed_type: 'texto', logical_state: 'valued',
      provenance: [], validation_state: 'pendiente', conflict_status: 'sin_conflicto', has_conflict: false,
      history: [], prefill_policy: 'solo_evidencia', prefill_presentation: 'casilla_vacia',
      proposed_value: null, prefill_options: [], prefill_warning: null,
    }],
  }],
}

it('exige motivo y conserva el actor al modificar', async () => {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === 'PUT') return new Response(JSON.stringify({ ...IDENTITY, display_name: 'Nombre corregido', version: 2 }))
    if (url.includes('/maintenance')) return new Response(JSON.stringify({ sequence: 1 }))
    if (url.includes('/records/record-1')) return new Response(JSON.stringify(SOURCE_RECORD))
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

  await waitFor(() => expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'PUT')).toBe(true))
  const updateCall = fetchMock.mock.calls.find(([, init]) => init?.method === 'PUT')
  const payload = JSON.parse(String(updateCall?.[1]?.body))
  expect(payload).toMatchObject({ actor_id: 'ana', expected_version: 1, reason: 'Corrección revisada.' })
})

it('edita campos importados sin enviar una decisión farmacéutica', async () => {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.includes('/maintenance')) return new Response(JSON.stringify({ sequence: 1 }))
    if (url.includes('/records/record-1')) return new Response(JSON.stringify(SOURCE_RECORD))
    if (url.includes('/history')) return new Response(JSON.stringify([]))
    if (url.includes('/relations')) return new Response(JSON.stringify([]))
    if (url.includes('/classifications')) return new Response(JSON.stringify([]))
    return new Response(JSON.stringify(IDENTITY))
  })
  vi.stubGlobal('fetch', fetchMock)
  render(<CatalogIdentityScreen identityId='dcp-1' reviewer={REVIEWER} />)

  await screen.findByRole('heading', { name: 'Campos importados' })
  expect(screen.getAllByText('Nombre original')).toHaveLength(2)
  fireEvent.click(screen.getByRole('button', { name: 'Editar campo' }))
  fireEvent.change(screen.getByLabelText('Nuevo valor para DESCRIPCION'), { target: { value: 'Nombre corregido' } })
  fireEvent.change(screen.getByLabelText('Motivo para DESCRIPCION'), { target: { value: 'Corrección de catálogo.' } })
  fireEvent.click(screen.getByRole('button', { name: 'Guardar' }))

  await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/maintenance'))).toBe(true))
  const maintenanceCall = fetchMock.mock.calls.find(([url]) => String(url).includes('/maintenance'))
  expect(JSON.parse(String(maintenanceCall?.[1]?.body))).toMatchObject({
    expected_sequence: 0, value: 'Nombre corregido', actor_id: 'ana', reason: 'Corrección de catálogo.',
  })
  expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/decisions'))).toBe(false)
})
