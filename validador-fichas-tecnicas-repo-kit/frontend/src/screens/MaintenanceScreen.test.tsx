import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { SessionContext } from '../auth/SessionContext'

import { MaintenanceScreen } from './MaintenanceScreen'

const SUMMARY = {
  id: 'event-1', nregistro: '51347', occurred_at_epoch: 1, change_type: 3,
  areas: ['ft'], old_version_id: 'old', new_version_id: 'new',
  affected_field_count: 2, has_diff: true, recorded_at: '2026-09-09T10:00:00+00:00',
}
const history = (items: unknown[], total = items.length, page = 1) => ({ items, total, page, page_size: 50 })

afterEach(() => vi.unstubAllGlobals())

it('muestra campos reabiertos y despliega el diff bajo demanda', async () => {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => ({
    ok: true,
    status: 200,
    json: async () => String(input).endsWith('/maintenance/runs')
      ? []
      : String(input).endsWith('/event-1')
        ? { ...SUMMARY, source_sha256: 'a'.repeat(64), fetched_at: SUMMARY.recorded_at,
          diff: { changes: [{ role: 'section', ordinal: 1, change_type: 'modified',
            old_locator: '4.2', new_locator: '4.2', diff_kind: 'text', text_diff: '-antes\n+después' }] } }
      : history([SUMMARY]),
  }) as Response))
  render(<MaintenanceScreen />)

  expect(await screen.findByText('51347')).toBeInTheDocument()
  expect(screen.getByText('2')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Ver detalle' }))
  expect(await screen.findByText('4.2')).toBeInTheDocument()
  expect(screen.getByText(/después/)).toBeInTheDocument()
})

it('resume los registros relacionados sin ocultar los enlaces adicionales', async () => {
  const catalog_targets = [1, 2, 3, 4].map((number) => ({
    identity_id: `identity-${number}`,
    display_name: `Medicamento ${number}`,
    identity_type: 'especialidad',
    national_code: String(number).padStart(6, '0'),
  }))
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => ({
    ok: true, status: 200,
    json: async () => String(input).endsWith('/maintenance/runs')
      ? [] : history([{ ...SUMMARY, catalog_targets }]),
  }) as Response))
  render(<MaintenanceScreen />)

  expect(await screen.findByText('4 registros del catálogo relacionados')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /Medicamento 1/ })).toHaveAttribute('href', '#/catalogo/identity-1')
  fireEvent.click(screen.getByText('Mostrar 2 registros más'))
  expect(screen.getByRole('link', { name: /Medicamento 4/ })).toHaveAttribute('href', '#/catalogo/identity-4')
})

it('permite recorrer el histórico y buscar un número de registro', async () => {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => ({
    ok: true, status: 200,
    json: async () => {
      const url = String(input)
      if (url.endsWith('/maintenance/runs')) return []
      if (url.includes('nregistro=70000')) return history([{ ...SUMMARY, id: 'filtered', nregistro: '70000' }])
      if (url.includes('page=2')) return history([{ ...SUMMARY, id: 'older', nregistro: 'older' }], 51, 2)
      return history([SUMMARY], 51)
    },
  }) as Response))
  render(<MaintenanceScreen />)

  expect(await screen.findByText('Mostrando 1–50 de 51 novedades conservadas.')).toBeInTheDocument()
  expect(screen.getAllByText('Página 1 de 2')).toHaveLength(2)
  fireEvent.click(screen.getAllByRole('button', { name: 'Más antiguas' })[0])
  expect(await screen.findByText('older')).toBeInTheDocument()
  expect(screen.getAllByText('Página 2 de 2')).toHaveLength(2)
  fireEvent.click(screen.getAllByRole('button', { name: 'Más recientes' })[0])
  expect(await screen.findByText('51347')).toBeInTheDocument()
  fireEvent.change(screen.getAllByRole('spinbutton', { name: 'Ir a la página' })[0], {
    target: { value: '2' },
  })
  fireEvent.click(screen.getAllByRole('button', { name: 'Ir' })[0])
  expect(await screen.findByText('older')).toBeInTheDocument()
  fireEvent.change(screen.getByRole('searchbox', { name: 'N.º registro CIMA' }), {
    target: { value: '70000' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Buscar' }))
  expect(await screen.findByText('70000')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Más antiguas' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Limpiar filtros · 1' }))
  expect(await screen.findByText('51347')).toBeInTheDocument()
  expect(screen.getAllByText('Página 1 de 2')).toHaveLength(2)
})

it('explica el estado vacío', async () => {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => ({
    ok: true, status: 200,
    json: async () => String(input).endsWith('/maintenance/runs') ? [] : history([]),
  }) as Response))
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
      : history([]),
  }) as Response))
  render(<MaintenanceScreen />)
  expect(await screen.findByRole('alert')).toHaveTextContent('La consulta automática CIMA lleva')
})

it('muestra el progreso de una recuperación en curso sin llamarla fallida', async () => {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => ({
    ok: true, status: 200,
    json: async () => String(input).endsWith('/maintenance/runs')
      ? [
          { id: 'current', requested_date: '30/09/2026', attempt: 6, status: 'running',
            event_count: 40, error_detail: null, started_at: SUMMARY.recorded_at,
            finished_at: null },
          { id: 'previous', requested_date: '29/09/2026', attempt: 1, status: 'completed',
            event_count: 1, error_detail: null, started_at: SUMMARY.recorded_at,
            finished_at: SUMMARY.recorded_at },
        ]
      : history([]),
  }) as Response))
  render(<MaintenanceScreen />)
  expect(await screen.findByText(/40 novedades nuevas procesadas/)).toBeInTheDocument()
  expect(screen.getByText('En curso · 40 novedades')).toBeInTheDocument()
  expect(screen.queryByText(/La consulta automática CIMA lleva/)).not.toBeInTheDocument()
})

it('hace visible el último fallo operativo y su intento', async () => {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => ({
    ok: true,
    status: 200,
    json: async () => String(input).endsWith('/maintenance/runs')
      ? [{ id: 'run', requested_date: '08/09/2026', attempt: 2, status: 'failed',
          event_count: 0, error_detail: 'CIMA no disponible',
          started_at: SUMMARY.recorded_at, finished_at: SUMMARY.recorded_at }]
      : history([]),
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
        : history([{ ...SUMMARY, new_version_id: null, has_diff: false }]),
  }) as Response))
  render(<MaintenanceScreen />)
  expect(await screen.findByText('51347')).toBeInTheDocument()
  expect(screen.getByText('La consulta CIMA terminó con documentos no disponibles')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Ver detalle' }))
  expect(await screen.findByText(/no ofrece sus secciones para este medicamento/)).toBeInTheDocument()
})

it('oculta la consulta manual a usuarios sin permiso para gestionar fuentes', async () => {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => ({
    ok: true, status: 200,
    json: async () => String(input).endsWith('/maintenance/runs') ? [] : history([]),
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
