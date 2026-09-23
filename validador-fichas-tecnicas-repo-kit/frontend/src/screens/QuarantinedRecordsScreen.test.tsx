import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import type { QuarantinedSourceRowPage, Reviewer } from '../api/types'
import { QuarantinedRecordsScreen } from './QuarantinedRecordsScreen'

const REVIEWER: Reviewer = {
  identifier: 'ana',
  display_name: 'Ana',
  assurance: 'declarada',
  role: 'farmaceutico',
  role_label: 'Farmacéutico',
  may_sign_pharmacist_states: true,
}

const page: QuarantinedSourceRowPage = {
  total: 1,
  items: [{
    id: 'q-1',
    source_workbook: 'Especialidades-CargaMaster190626.xlsx',
    source_locator: 'Excipientes!42',
    reason_code: 'MISSING_PARENT',
    reason: 'No existe una especialidad padre inequívoca.',
    fields: [{
      source_column_index: 1,
      field_name: 'BN_DESCRIPCION',
      literal_value: 'Excipiente',
      maintained_value: 'Excipiente',
      observed_type: 'texto',
      maintenance_sequence: 0,
      maintenance_history: [],
    }],
  }],
}

afterEach(() => vi.unstubAllGlobals())

it('permite corregir celdas de cuarentena sin cambiar el motivo ni el literal fuente', async () => {
  const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (init?.method === 'POST' && url.includes('/maintenance')) {
      return { ok: true, status: 201, json: async () => ({ maintenance_sequence: 1 }) } as Response
    }
    return { ok: true, status: 200, json: async () => page } as Response
  })
  vi.stubGlobal('fetch', mock)
  render(<QuarantinedRecordsScreen reviewer={REVIEWER} />)

  await screen.findByText('No existe una especialidad padre inequívoca.')
  fireEvent.click(screen.getByRole('button', { name: 'Editar campo' }))
  fireEvent.change(screen.getByLabelText('Nuevo valor para BN_DESCRIPCION'), {
    target: { value: 'Excipiente corregido' },
  })
  fireEvent.change(screen.getByLabelText('Motivo'), { target: { value: 'Corrección de prueba' } })
  fireEvent.click(screen.getByRole('button', { name: 'Guardar' }))

  await waitFor(() => expect(mock.mock.calls.some(([url, init]) =>
    String(url).includes('/records/quarantined/q-1/values/1/maintenance') && init?.method === 'POST',
  )).toBe(true))
  const payload = mock.mock.calls.find(([url, init]) =>
    String(url).includes('/records/quarantined/q-1/values/1/maintenance') && init?.method === 'POST',
  )?.[1]?.body
  expect(JSON.parse(String(payload))).toMatchObject({
    expected_sequence: 0,
    value: 'Excipiente corregido',
    actor_id: 'ana',
    reason: 'Corrección de prueba',
  })
  expect(mock.mock.calls.some(([url]) => String(url).includes('/decisions'))).toBe(false)
})
