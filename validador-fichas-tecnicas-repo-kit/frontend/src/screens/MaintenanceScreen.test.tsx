import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import type { MaintenanceAction } from '../api/client'
import type { Reviewer } from '../api/types'
import { SessionContext } from '../auth/SessionContext'

import { MaintenanceScreen } from './MaintenanceScreen'

const SUMMARY = {
  id: 'event-1', nregistro: '51347', occurred_at_epoch: 1, change_type: 3,
  areas: ['ft'], old_version_id: 'old', new_version_id: 'new',
  affected_field_count: 2, has_diff: true, recorded_at: '2026-09-09T10:00:00+00:00',
}
const history = (items: unknown[], total = items.length, page = 1) => ({ items, total, page, page_size: 50 })

afterEach(() => vi.unstubAllGlobals())

const EMPTY_ACTIONS = { items: [], total: 0, limit: 200, offset: 0, origin: 'real', counts: {} }

/** Las acciones (bandeja e histórico de decisiones) se sirven aparte de los avisos. */
function withActions(handler: (input: RequestInfo | URL) => Promise<Response>) {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    if (url.includes('/maintenance/actions/unlinked')) {
      return { ok: true, status: 200, json: async () => ({ items: [], page: 1, page_size: 50, total: 0 }) } as Response
    }
    if (url.includes('/maintenance/actions')) {
      return { ok: true, status: 200, json: async () => EMPTY_ACTIONS } as Response
    }
    return handler(input)
  })
}

it('muestra campos reabiertos y despliega el diff bajo demanda', async () => {
  vi.stubGlobal('fetch', withActions(async (input: RequestInfo | URL) => ({
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
  fireEvent.click(await screen.findByRole('tab', { name: 'Histórico' }))

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
  vi.stubGlobal('fetch', withActions(async (input: RequestInfo | URL) => ({
    ok: true, status: 200,
    json: async () => String(input).endsWith('/maintenance/runs')
      ? [] : history([{ ...SUMMARY, catalog_targets }]),
  }) as Response))
  render(<MaintenanceScreen />)
  fireEvent.click(await screen.findByRole('tab', { name: 'Histórico' }))

  expect(await screen.findByText('4 registros del catálogo relacionados')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /Medicamento 1/ })).toHaveAttribute('href', '#/catalogo/identity-1')
  fireEvent.click(screen.getByText('Mostrar 2 registros más'))
  expect(screen.getByRole('link', { name: /Medicamento 4/ })).toHaveAttribute('href', '#/catalogo/identity-4')
})

it('permite recorrer el histórico y buscar un número de registro', async () => {
  vi.stubGlobal('fetch', withActions(async (input: RequestInfo | URL) => ({
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
  fireEvent.click(await screen.findByRole('tab', { name: 'Histórico' }))

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
  vi.stubGlobal('fetch', withActions(async (input: RequestInfo | URL) => ({
    ok: true, status: 200,
    json: async () => String(input).endsWith('/maintenance/runs') ? [] : history([]),
  }) as Response))
  render(<MaintenanceScreen />)
  fireEvent.click(await screen.findByRole('tab', { name: 'Histórico' }))
  expect(await screen.findByText('Sin novedades')).toBeInTheDocument()
  expect(await screen.findByRole('alert')).toHaveTextContent('Todavía no hay una consulta automática CIMA completada')
})

it('advierte cuando la última consulta completa quedó atrasada', async () => {
  vi.stubGlobal('fetch', withActions(async (input: RequestInfo | URL) => ({
    ok: true, status: 200,
    json: async () => String(input).endsWith('/maintenance/runs')
      ? [{ id: 'run', requested_date: '08/09/2026', attempt: 1, status: 'completed',
          event_count: 0, error_detail: null, started_at: SUMMARY.recorded_at,
          finished_at: SUMMARY.recorded_at }]
      : history([]),
  }) as Response))
  render(<MaintenanceScreen />)
  fireEvent.click(await screen.findByRole('tab', { name: 'Histórico' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('La consulta automática CIMA lleva')
})

it('muestra el progreso de una recuperación en curso sin llamarla fallida', async () => {
  vi.stubGlobal('fetch', withActions(async (input: RequestInfo | URL) => ({
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
  fireEvent.click(await screen.findByRole('tab', { name: 'Histórico' }))
  expect(await screen.findByText(/40 novedades nuevas procesadas/)).toBeInTheDocument()
  expect(screen.getByText('En curso · 40 novedades')).toBeInTheDocument()
  expect(screen.queryByText(/La consulta automática CIMA lleva/)).not.toBeInTheDocument()
})

it('hace visible el último fallo operativo y su intento', async () => {
  vi.stubGlobal('fetch', withActions(async (input: RequestInfo | URL) => ({
    ok: true,
    status: 200,
    json: async () => String(input).endsWith('/maintenance/runs')
      ? [{ id: 'run', requested_date: '08/09/2026', attempt: 2, status: 'failed',
          event_count: 0, error_detail: 'CIMA no disponible',
          started_at: SUMMARY.recorded_at, finished_at: SUMMARY.recorded_at }]
      : history([]),
  }) as Response))
  render(<MaintenanceScreen />)
  fireEvent.click(await screen.findByRole('tab', { name: 'Histórico' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('La última consulta CIMA falló')
  expect(screen.getByRole('alert')).toHaveTextContent('intento 2')
})

it('explica los avisos de ficha técnica sin secciones disponibles', async () => {
  vi.stubGlobal('fetch', withActions(async (input: RequestInfo | URL) => ({
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
  fireEvent.click(await screen.findByRole('tab', { name: 'Histórico' }))
  expect(await screen.findByText('51347')).toBeInTheDocument()
  expect(screen.getByText('La consulta CIMA terminó con documentos no disponibles')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Ver detalle' }))
  expect(await screen.findByText(/no ofrece sus secciones para este medicamento/)).toBeInTheDocument()
})

it('oculta la consulta manual a usuarios sin permiso para gestionar fuentes', async () => {
  vi.stubGlobal('fetch', withActions(async (input: RequestInfo | URL) => ({
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

const REVIEWER = { identifier: 'ana', display_name: 'Ana', assurance: 'declarada' } as Reviewer

function action(overrides: Partial<MaintenanceAction>): MaintenanceAction {
  return {
    id: 'a1', event_id: 'e1', kind: 'revisar_estado', area: 'estado', data_origin: 'real',
    state: 'pendiente', sequence: 0, nregistro: '51347', event_occurred_at_epoch: 1_761_800_000_000,
    event_change_type: 3, target_record_id: 'rec-1', identity_id: 'ident-1',
    identity_name: 'Omeprazol 20 mg', national_code: '600000', master_field_name: 'ACTIVO',
    master_value_literal: 'S', cima_version_id: 'v1', cima_pointer: '/estado',
    cima_value_literal: '{"aut":1,"susp":2}', cima_fetched_at: '2026-10-30T09:00:00+00:00',
    cima_source_url: 'https://cima.aemps.es/cima/rest/presentacion/600000',
    proposed_value: null, rule_id: null, proposal: null, diagnostic_code: 'sin_correspondencia',
    derivation_version: 'novedades-v1', last_decision: null, ...overrides,
  }
}

function actionsServer(items: MaintenanceAction[], counts: Record<string, number>) {
  const calls: Array<{ url: string, init?: RequestInit }> = []
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    calls.push({ url, init })
    const body = url.endsWith('/maintenance/runs') ? []
      : url.includes('/maintenance/actions/unlinked')
        ? { items: [{ id: 'u1', nregistro: 'zzz', occurred_at_epoch: 1_761_800_000_000, change_type: 3,
          areas: ['prosp'], recorded_at: SUMMARY.recorded_at, diagnostic_code: 'sin_registro_en_catalogo' }],
        page: 1, page_size: 50, total: 1 }
        : url.includes('/send-to-review') ? { enqueued: ['rec-1'], already_queued: [], decided: ['a1'], rejected: [] }
          : url.includes('/decisions') ? { sequence: 1, decision: 'descartada', reason: 'x' }
            : url.includes('/maintenance/actions/history')
              ? { items: [], total: 0, limit: 50, offset: 0, origin: 'real', counts: {} }
              : url.includes('/maintenance/actions')
                ? { items, total: items.length, limit: 200, offset: 0, origin: 'real', counts }
                : history([])
    return { ok: true, status: 200, json: async () => body } as Response
  }))
  return calls
}

const ALTA = action({
  id: 'a2', kind: 'proponer_alta', target_record_id: null, identity_id: null,
  identity_name: null, national_code: '777777',
  proposal: { workbook: 'especialidades', sheet: 'General', columns: [
    { column: 1, name: 'CODIGO_NACIONAL', value: '777777', provenance: null, diagnostic: null },
    { column: 2, name: 'ME_DESCRIPCION', value: null, provenance: null, diagnostic: 'sin_fuente' },
  ] },
})

it('abre en Por atender, cuenta solo acciones con registro y agrupa por tipo sin preselección', async () => {
  actionsServer([action({}), ALTA], { revisar_estado: 1, proponer_alta: 4 })
  render(<MaintenanceScreen reviewer={REVIEWER} />)

  expect(await screen.findByRole('tab', { name: 'Por atender', selected: true })).toBeInTheDocument()
  expect(screen.getByRole('tab', { name: 'Histórico' })).toBeInTheDocument()
  expect(screen.getByRole('tab', { name: 'Sin registro en el catálogo' })).toBeInTheDocument()
  const figures = await screen.findByLabelText('Novedades por atender')
  expect(figures).toHaveTextContent('Revisar estado en CIMA1')
  expect(figures).not.toHaveTextContent('Proponer alta')
  expect(screen.getByRole('heading', { name: 'Revisar estado en CIMA' })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Proponer alta' })).toBeInTheDocument()
  // Valor en CIMA con su fecha, sin valor propuesto y ningún control marcado.
  expect(screen.getByText(/Valor en CIMA a fecha/)).toBeInTheDocument()
  expect(screen.getByText('Sin valor propuesto: no hay correspondencia aceptada')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Ver procedencia' })).toHaveAttribute('href', expect.stringContaining('presentacion/600000'))
  screen.getAllByRole('checkbox').forEach(box => expect(box).not.toBeChecked())
  // El alta muestra las columnas exactas del maestro y marca lo que no tiene fuente.
  expect(screen.getByRole('columnheader', { name: 'ME_DESCRIPCION' })).toBeInTheDocument()
  expect(screen.getByText('sin fuente')).toBeInTheDocument()
})

it('muestra la propuesta ACTIVO = N con su regla y no la aplica sola', async () => {
  const calls = actionsServer([action({
    id: 'a3', kind: 'proponer_activo_n', proposed_value: 'N', rule_id: 'ADR-0019:baja-revocacion-activo:v1',
  })], { proponer_activo_n: 1 })
  render(<MaintenanceScreen reviewer={REVIEWER} />)

  expect(await screen.findByText('ACTIVO = N')).toBeInTheDocument()
  expect(screen.getByText(/ADR-0019:baja-revocacion-activo:v1/)).toBeInTheDocument()
  expect(calls.some(call => call.init?.method === 'POST')).toBe(false)
})

it('exige justificación para descartar y envía la decisión con el actor', async () => {
  const calls = actionsServer([action({})], { revisar_estado: 1 })
  render(<MaintenanceScreen reviewer={REVIEWER} />)

  fireEvent.click(await screen.findByRole('button', { name: 'Descartar' }))
  const confirm = screen.getByRole('button', { name: 'Confirmar' })
  expect(confirm).toBeDisabled()
  expect(calls.some(call => call.url.includes('/decisions'))).toBe(false)
  fireEvent.change(screen.getByLabelText('Justificación'), { target: { value: 'No procede' } })
  fireEvent.click(confirm)

  await waitFor(() => expect(calls.some(call => call.url.includes('/decisions'))).toBe(true))
  const call = calls.find(item => item.url.includes('/decisions'))!
  expect(JSON.parse(String(call.init?.body))).toEqual({
    actor_id: 'ana', decision: 'descartada', reason: 'No procede', expected_sequence: 0,
  })
})

it('marca como revisada sin pedir justificación y archiva solo con ella', async () => {
  const calls = actionsServer([
    action({}), action({ id: 'a4', kind: 'revisar_archivo', identity_name: 'Otro', master_value_literal: 'activa' }),
  ], { revisar_estado: 1, revisar_archivo: 1 })
  render(<MaintenanceScreen reviewer={REVIEWER} />)

  fireEvent.click(await screen.findByRole('button', { name: 'Marcar revisada' }))
  await waitFor(() => expect(calls.filter(call => call.url.includes('/decisions'))).toHaveLength(1))
  // La bandeja se recarga tras decidir; se espera a que vuelva a estar disponible.
  await waitFor(() => expect(calls.filter(call => /actions\?limit=200/.test(call.url))).toHaveLength(2))
  fireEvent.click(await screen.findByRole('button', { name: 'Archivar' }))
  expect(await screen.findByLabelText('Justificación')).toBeInTheDocument()
  expect(calls.filter(call => call.url.includes('/decisions'))).toHaveLength(1)
})

it('envía a Revisión en lote solo lo que seleccionas', async () => {
  const calls = actionsServer([
    action({}), action({ id: 'a5', target_record_id: 'rec-2', identity_name: 'Segundo' }),
  ], { revisar_estado: 2 })
  render(<MaintenanceScreen reviewer={REVIEWER} />)

  const send = await screen.findByRole('button', { name: /Enviar a Revisión \(0\)/ })
  expect(send).toBeDisabled()
  fireEvent.click(screen.getByRole('checkbox', { name: 'Seleccionar Omeprazol 20 mg' }))
  fireEvent.click(screen.getByRole('button', { name: /Enviar a Revisión \(1\)/ }))

  await waitFor(() => expect(calls.some(call => call.url.includes('/send-to-review'))).toBe(true))
  const call = calls.find(item => item.url.includes('/send-to-review'))!
  expect(JSON.parse(String(call.init?.body))).toEqual({ actor_id: 'ana', action_ids: ['a1'] })
  expect(await screen.findByText(/1 registros encolados/)).toBeInTheDocument()
})

it('lista aparte los avisos sin registro en el catálogo', async () => {
  actionsServer([], {})
  render(<MaintenanceScreen reviewer={REVIEWER} />)
  fireEvent.click(await screen.findByRole('tab', { name: 'Sin registro en el catálogo' }))
  expect(await screen.findByRole('rowheader', { name: 'zzz' })).toBeInTheDocument()
  expect(screen.getByText(/no generan acciones/)).toBeInTheDocument()
})

it('avisa de que no hay nada que escribir si el maestro ya dice N', async () => {
  actionsServer([action({
    id: 'a6', kind: 'proponer_activo_n', proposed_value: 'N', master_value_literal: 'N',
    rule_id: 'ADR-0019:baja-revocacion-activo:v1',
  })], { proponer_activo_n: 1 })
  render(<MaintenanceScreen reviewer={REVIEWER} />)
  expect(await screen.findByText(/ya dice ACTIVO = N: aceptar solo registra tu decisión/)).toBeInTheDocument()
})
