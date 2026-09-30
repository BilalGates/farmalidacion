import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { SourcesScreen } from './SourcesScreen'

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
    fireEvent.click(await screen.findByRole('button', { name: 'Ver detalle' }))
    expect(await screen.findByRole('heading', { name: workbook.label })).toBeInTheDocument()
    for (const sheet of workbook.sheets) expect(screen.getByRole('row', { name: new RegExp(sheet) })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: workbook.action }))
    expect(JSON.parse(sessionStorage.getItem('farmalidacion.catalog-list-state') ?? '{}').sourceWorkbook).toBe(workbook.view)
    expect(window.location.hash).toBe('#/fichas')
  })
}
