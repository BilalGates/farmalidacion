import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { groupSources, SourcesScreen } from './SourcesScreen'

const ITEMS = [
  { key: 'doc-1', name: '00134033', source_type: 'cima_document_type_1', status: 'disponible', versions: 1,
    latest_version: null, latest_content_hash: 'a', last_updated_at: '2026-08-28T10:32:00Z', batches: 0,
    records: 1, diagnostics: 0, quarantined_rows: 0 },
  { key: 'doc-2', name: '00150004', source_type: 'cima_document_type_1', status: 'con_errores', versions: 1,
    latest_version: null, latest_content_hash: 'b', last_updated_at: '2026-08-28T10:33:00Z', batches: 2,
    records: 3, diagnostics: 1, quarantined_rows: 2 },
]

afterEach(() => vi.unstubAllGlobals())

it('agrega los documentos del mismo tipo sin perder sus incidencias', () => {
  expect(groupSources(ITEMS)).toMatchObject([{
    sourceType: 'cima_document_type_1', label: 'CIMA · Ficha técnica', status: 'con_errores',
    records: 4, batches: 2, incidents: 3, lastUpdatedAt: '2026-08-28T10:33:00Z',
  }])
})

it('muestra un grupo y permite desplegar sus documentos', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => ({
    ok: true, status: 200, json: async () => ({ items: ITEMS, total: ITEMS.length }),
  }) as Response))
  render(<SourcesScreen />)

  const toggle = await screen.findByRole('button', { name: /CIMA · Ficha técnica 2 documentos/ })
  expect(screen.queryByText('00134033')).not.toBeInTheDocument()
  fireEvent.click(toggle)
  expect(screen.getByText('00134033')).toBeInTheDocument()
  expect(screen.getByText('00150004')).toBeInTheDocument()
  expect(screen.getAllByRole('button', { name: 'Ver detalle' })).toHaveLength(2)
})
