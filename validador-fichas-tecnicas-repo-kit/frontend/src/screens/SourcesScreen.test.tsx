import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { SourcesScreen } from './SourcesScreen'
import { SessionContext } from '../auth/SessionContext'

afterEach(() => {
  vi.unstubAllGlobals()
  window.sessionStorage.removeItem('farmalidacion.catalog-list-state')
  window.location.hash = ''
})

const workbooks = [
  { name: 'Especialidades-CargaMaster190626.xlsx', label: 'Especialidades y presentaciones', action: 'Explorar presentaciones', view: 'especialidades', sheets: ['General', 'Excipientes'] },
  { name: 'Medicamento-cargaMaster25062026.xlsx', label: 'Medicamentos', action: 'Explorar medicamentos', view: 'medicamentos', sheets: ['General', 'Composicion', 'Indicacion', 'Frecuencia', 'Via', 'Prescripcion', 'Links'] },
  { name: 'PrincipioActivoCargaMaster-22062026.xlsx', label: 'Principios activos', action: 'Explorar principios activos', view: 'principios_activos', sheets: ['General', 'Frecuencia', 'Via', 'ConsejosAdministracion', 'DatosAnaliticos'] },
] as const

it('separa la consulta de BOT PLUS de su integración y pliega la configuración SQL Server', async () => {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => new Response(JSON.stringify(
    String(input).includes('/nomenclator/snapshot')
      ? { available: true, sha256: 'a'.repeat(64), row_count: 35228, latest_source_date: '2026-10-01' }
      : String(input).includes('/source-connections/nomenclator')
      ? { configured: false, host: null, port: 1433, database_name: null, username: null, server_password_configured: false, updated_at: null }
      : { items: [], total: 0 },
  ))))
  render(<SourcesScreen />)

  expect(await screen.findByRole('heading', { name: 'BOT PLUS' })).toBeInTheDocument()
  const bot = screen.getByRole('region', { name: 'BOT PLUS' })
  expect(bot).toHaveTextContent('Sin conectar')
  expect(bot).toHaveTextContent('BOT PLUS Integración')
  expect(screen.getByRole('link', { name: 'Abrir BOT PLUS Web' })).toHaveAttribute('href', 'https://botplusweb.farmaceuticos.com/')
  fireEvent.click(screen.getByText('Qué falta para conectar BOT PLUS Integración'))
  expect(bot).toHaveTextContent('Configurar después las credenciales mediante un secreto del servidor.')

  const toggle = screen.getByRole('button', { name: 'Configurar conexión' })
  expect(await screen.findByText('Para actualizar tu Nomenclátor necesitas una sesión corporativa.')).toBeVisible()
  expect(screen.getByRole('region', { name: 'Mi Nomenclátor' })).toHaveTextContent('35.228')
  expect(toggle).toHaveAttribute('aria-expanded', 'false')
  fireEvent.click(toggle)
  expect(screen.getByRole('button', { name: 'Ocultar configuración' })).toHaveAttribute('aria-expanded', 'true')
  expect(screen.getByRole('textbox', { name: 'Servidor' })).toBeInTheDocument()
})

it('permite sincronizar al lector con su conector local sin mostrar la configuración central', async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (url === 'http://127.0.0.1:8765/health') return new Response(JSON.stringify({ ready: true, version: '2', busy: false }))
    if (url.startsWith('http://127.0.0.1:8765/')) return new Response(new Blob(['copia local']))
    if (url.includes('/nomenclator/snapshots') && init?.method === 'POST') return new Response(JSON.stringify({
      available: true, sha256: 'a'.repeat(64), row_count: 35228,
      latest_source_date: '2026-10-01', changed: true,
      changes: { previous_sha256: null, added: 35228, removed: 0, modified: 0, sample_added: [], sample_removed: [], sample_modified: [] },
    }))
    if (url.includes('/nomenclator/snapshot')) return new Response(JSON.stringify({ available: false, sha256: null, row_count: 0, latest_source_date: null }))
    return new Response(JSON.stringify({ items: [], total: 0 }))
  })
  vi.stubGlobal('fetch', fetchMock)
  render(<SessionContext.Provider value={{
    subject_id: 'entra:test:reader', capabilities: ['sources.read'], logout: () => {},
    reviewer: { identifier: 'ana', display_name: 'Ana', role: 'tecnico',
      role_label: 'Técnico', assurance: 'verificada_entra', may_sign_pharmacist_states: false },
  }}><SourcesScreen /></SessionContext.Provider>)
  expect(await screen.findByRole('heading', { name: 'Mi Nomenclátor' })).toBeVisible()
  expect(screen.queryByText('Acceso restringido')).not.toBeInTheDocument()
  const update = screen.getByRole('button', { name: 'Actualizar datos' })
  await waitFor(() => expect(update).toBeEnabled())
  fireEvent.click(update)
  await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/nomenclator/snapshots'))).toBe(true))
  const localCall = fetchMock.mock.calls.find(([url]) => String(url) === 'http://127.0.0.1:8765/snapshot')
  expect(JSON.parse(String(localCall?.[1]?.body))).toMatchObject({ server: 'localhost', auth: 'windows' })
  expect(await screen.findByText('Datos actualizados: 35.228 registros verificados y guardados.')).toBeVisible()
  expect(screen.getByText(/Primera versión/)).toHaveTextContent('35.228')
})

it('muestra la copia guardada y no la marca como pendiente cuando el conector está cerrado', async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    if (url.startsWith('http://127.0.0.1:8765/')) throw new TypeError('Failed to fetch')
    if (url.includes('/nomenclator/snapshot')) return new Response(JSON.stringify({
      available: true, sha256: 'b'.repeat(64), row_count: 35228, latest_source_date: '2026-10-01',
      version_id: 3, synced_at: '2026-10-20T10:00:00+00:00', version_count: 3,
    }))
    return new Response(JSON.stringify({ items: [], total: 0 }))
  })
  vi.stubGlobal('fetch', fetchMock)
  render(<SessionContext.Provider value={{
    subject_id: 'entra:test:reader', capabilities: ['sources.read'], logout: () => {},
    reviewer: { identifier: 'ana', display_name: 'Ana', role: 'tecnico',
      role_label: 'Técnico', assurance: 'verificada_entra', may_sign_pharmacist_states: false },
  }}><SourcesScreen /></SessionContext.Provider>)
  const panel = await screen.findByRole('region', { name: 'Mi Nomenclátor' })
  await waitFor(() => expect(panel).toHaveTextContent('No detectado'))
  expect(panel).toHaveTextContent('Datos disponibles')
  expect(panel).toHaveTextContent('35.228')
  expect(panel).not.toHaveTextContent(/pendiente/i)
  expect(screen.getByRole('button', { name: 'Actualizar datos' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Ver información' })).toBeEnabled()
  expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/nomenclator/snapshots'))).toBe(false)
})

for (const [index, workbook] of workbooks.entries()) {
  it(`distingue ${workbook.view} y muestra todas sus hojas`, async () => {
    const source = {
      key: `source-${index}`, name: workbook.name, source_type: 'master_excel',
      status: 'disponible', versions: 1, latest_version: null, latest_content_hash: 'a'.repeat(64),
      last_updated_at: null, batches: 1, records: 10, diagnostics: 0, quarantined_rows: 0,
    }
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => new Response(JSON.stringify(
      String(input).endsWith(`/sources/${source.key}`)
        ? { ...source, sheets: workbook.sheets.map((sheet_name, sheet_ordinal) => ({
          sheet_name, sheet_ordinal: sheet_ordinal + 1,
          data_row_count: sheet_ordinal === 0 ? 10 : 0, material_value_count: sheet_ordinal === 0 ? 20 : 0,
        })), batch_ids: ['batch-1'] }
        : { items: [source], total: 1 },
    ))))

    render(<SourcesScreen />)
    fireEvent.click(await screen.findByRole('button', { name: 'Gestionar y ver versiones' }))
    expect(await screen.findByRole('heading', { name: workbook.label })).toBeInTheDocument()
    for (const sheet of workbook.sheets) expect(screen.getByRole('row', { name: new RegExp(sheet) })).toBeInTheDocument()
    fireEvent.click(screen.getAllByRole('button', { name: workbook.action })[0])
    expect(JSON.parse(sessionStorage.getItem('farmalidacion.catalog-list-state') ?? '{}').sourceWorkbook).toBe(workbook.view)
    expect(window.location.hash).toBe('#/fichas')
  })
}
