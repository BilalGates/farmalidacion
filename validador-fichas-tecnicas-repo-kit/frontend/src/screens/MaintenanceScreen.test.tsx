import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { SessionContext } from '../auth/SessionContext'

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
  expect(await screen.findByRole('alert')).toHaveTextContent('Todavía no hay una consulta automática CIMA completada')
})

it('advierte cuando la última consulta completa quedó atrasada', async () => {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => ({
    ok: true, status: 200,
    json: async () => String(input).endsWith('/maintenance/runs')
      ? [{ id: 'run', requested_date: '08/09/2026', attempt: 1, status: 'completed',
          event_count: 0, error_detail: null, started_at: SUMMARY.recorded_at,
          finished_at: SUMMARY.recorded_at }]
      : [],
  }) as Response))
  render(<MaintenanceScreen />)
  expect(await screen.findByRole('alert')).toHaveTextContent('La consulta automática CIMA lleva')
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

it('explica los avisos de ficha técnica sin secciones disponibles', async () => {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => ({
    ok: true,
    status: 200,
    json: async () => String(input).endsWith('/maintenance/runs')
      ? [{ id: 'run', requested_date: '20/10/2026', attempt: 1, status: 'completed',
          event_count: 1, error_detail: '1 aviso de ficha técnica sin secciones disponibles en CIMA.',
          started_at: SUMMARY.recorded_at, finished_at: SUMMARY.recorded_at }]
      : String(input).endsWith('/event-1')
        ? { ...SUMMARY, new_version_id: null, has_diff: false, diff: null,
            source_sha256: 'a'.repeat(64), fetched_at: SUMMARY.recorded_at }
        : [{ ...SUMMARY, new_version_id: null, has_diff: false }],
  }) as Response))
  render(<MaintenanceScreen />)
  expect(await screen.findByText('51347')).toBeInTheDocument()
  expect(screen.getByRole('alert')).toHaveTextContent('documentos no disponibles')
  fireEvent.click(screen.getByRole('button', { name: 'Ver' }))
  expect(await screen.findByText(/no ofrece sus secciones para este medicamento/)).toBeInTheDocument()
})

it('oculta la consulta manual a usuarios sin permiso para gestionar fuentes', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => ({
    ok: true, status: 200, json: async () => [],
  }) as Response))
  render(
    <SessionContext.Provider value={{
      subject_id: 'user', reviewer: {
        identifier: 'user', display_name: 'Usuario', assurance: 'entra', role: 'tecnico',
        role_label: 'Técnico', may_sign_pharmacist_states: false,
      },
      capabilities: ['sources.read'], logout: vi.fn(),
    }}>
      <MaintenanceScreen />
    </SessionContext.Provider>,
  )
  expect(await screen.findByText('Sin novedades')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Consultar ayer' })).not.toBeInTheDocument()
})
