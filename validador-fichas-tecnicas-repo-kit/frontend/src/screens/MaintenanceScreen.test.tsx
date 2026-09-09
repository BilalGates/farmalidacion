import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { MaintenanceScreen } from './MaintenanceScreen'

const SUMMARY = {
  id: 'event-1', nregistro: '51347', occurred_at_epoch: 1, change_type: 3,
  areas: ['ft'], old_version_id: 'old', new_version_id: 'new',
  affected_field_count: 2, has_diff: true, recorded_at: '2026-09-09T10:00:00+00:00',
}

afterEach(() => vi.unstubAllGlobals())

it('muestra campos reabiertos y despliega el diff bajo demanda', async () => {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => ({
    ok: true,
    status: 200,
    json: async () => String(input).endsWith('/event-1')
      ? { ...SUMMARY, source_sha256: 'a'.repeat(64), fetched_at: SUMMARY.recorded_at,
          diff: { changes: [{ role: 'section', ordinal: 1, change_type: 'modified',
            old_locator: '4.2', new_locator: '4.2', diff_kind: 'text', text_diff: '-antes\n+después' }] } }
      : [SUMMARY],
  }) as Response))
  render(<MaintenanceScreen />)

  expect(await screen.findByText('51347')).toBeInTheDocument()
  expect(screen.getByText('2')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Ver' }))
  expect(await screen.findByText('4.2')).toBeInTheDocument()
  expect(screen.getByText(/después/)).toBeInTheDocument()
})

it('explica el estado vacío', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, status: 200, json: async () => [] }) as Response))
  render(<MaintenanceScreen />)
  expect(await screen.findByText('Sin novedades')).toBeInTheDocument()
})

it('hace visible el último fallo operativo y su intento', async () => {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => ({
    ok: true,
    status: 200,
    json: async () => String(input).endsWith('/maintenance/runs')
      ? [{ id: 'run', requested_date: '08/09/2026', attempt: 2, status: 'failed',
          event_count: 0, error_detail: 'CIMA no disponible',
          started_at: SUMMARY.recorded_at, finished_at: SUMMARY.recorded_at }]
      : [],
  }) as Response))
  render(<MaintenanceScreen />)

  expect(await screen.findByRole('alert')).toHaveTextContent('La última consulta CIMA falló')
  expect(screen.getByRole('alert')).toHaveTextContent('intento 2')
})
