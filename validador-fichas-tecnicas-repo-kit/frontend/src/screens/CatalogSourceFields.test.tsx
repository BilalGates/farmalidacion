import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import type { Reviewer } from '../api/types'
import { SourceFieldsMaintenance } from './CatalogSourceFields'

afterEach(() => vi.unstubAllGlobals())

it('completa una celda vacía con columna, actor y motivo', async () => {
  const record = {
    id: 'record-1', entity_type: 'medication', external_identifiers: [], blocks: [{
      id: 'block-1', block_type: 'General', ordinal: 1, values: [{
        id: 'field-1', field_name: 'IDEXTERNO', source_column_index: 1,
        literal_value: '123', maintained_value: '123', maintenance_sequence: 0,
        maintenance_history: [], observed_type: 'texto', logical_state: 'valued',
        provenance: [], validation_state: 'pendiente', conflict_status: 'sin_conflicto',
        has_conflict: false, history: [], prefill_policy: 'solo_evidencia',
        prefill_presentation: 'casilla_vacia', proposed_value: null, prefill_options: [],
        prefill_warning: null,
      }],
    }],
  }
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/empty-source-columns')) return new Response(JSON.stringify([
      { source_column_index: 2, field_name: 'DESCRIPCION' },
    ]))
    if (url.endsWith('/empty-source-values') && init?.method === 'POST') return new Response(JSON.stringify({ id: 'field-2' }))
    return new Response(JSON.stringify(record))
  })
  vi.stubGlobal('fetch', fetchMock)
  const reviewer = { identifier: 'ana', display_name: 'Ana', assurance: 'declarada' } as Reviewer
  render(<SourceFieldsMaintenance recordId='record-1' reviewer={reviewer} />)

  fireEvent.click(await screen.findByRole('button', { name: 'Completar celda vacía' }))
  await screen.findByRole('option', { name: 'DESCRIPCION · columna 2' })
  fireEvent.change(screen.getByLabelText('Valor para la celda vacía'), { target: { value: 'Valor nuevo' } })
  fireEvent.change(screen.getByLabelText('Motivo para completar la celda'), { target: { value: 'Revisión del maestro' } })
  fireEvent.click(screen.getByRole('button', { name: 'Guardar celda' }))

  await waitFor(() => expect(fetchMock.mock.calls.some(([url, init]) => url.endsWith('/empty-source-values') && init?.method === 'POST')).toBe(true))
  const call = fetchMock.mock.calls.find(([url, init]) => url.endsWith('/empty-source-values') && init?.method === 'POST')
  expect(JSON.parse(String(call?.[1]?.body))).toEqual({
    source_column_index: 2, value: 'Valor nuevo', actor_id: 'ana', reason: 'Revisión del maestro',
  })
  expect(fetchMock.mock.calls.every(([url]) => !url.includes('/decisions'))).toBe(true)
})
