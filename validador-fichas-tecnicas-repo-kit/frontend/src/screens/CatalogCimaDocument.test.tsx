import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { CatalogCimaDocumentReader } from './CatalogCimaDocument'

afterEach(() => vi.unstubAllGlobals())

it('indica cuando no hay vínculo CIMA verificado', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify([]))))
  render(<CatalogCimaDocumentReader identityId='presentation-1' />)
  expect(await screen.findByText(/No hay una ficha técnica CIMA vinculada/)).toBeInTheDocument()
})

it('muestra la versión vinculada y busca apartados sin ejecutar su HTML', async () => {
  const fetchMock = vi.fn(async () => new Response(JSON.stringify([{
    document_name: '51347', document_version_id: 'version-2', source_version: '2026-09',
    content_hash: 'a'.repeat(64), acquired_at: '2026-09-25T08:00:00Z',
    sections: [
      { locator: '1', literal_text: '<script>window.bad = true</script>Composición' },
      { locator: '4.2', literal_text: 'Posología literal' },
    ],
  }])))
  vi.stubGlobal('fetch', fetchMock)
  render(<CatalogCimaDocumentReader identityId='presentation-1' />)
  expect(await screen.findByRole('heading', { name: 'Registro CIMA 51347' })).toBeInTheDocument()
  expect(screen.getByText(/Versión 2026-09/)).toBeInTheDocument()
  expect(document.querySelector('.catalog-cima script')).toBeNull()
  fireEvent.change(screen.getByRole('searchbox', { name: 'Buscar en los apartados' }), { target: { value: '4.2' } })
  expect(screen.getByText('Posología literal')).toBeInTheDocument()
  expect(screen.queryByText(/window.bad/)).toBeNull()
  expect(fetchMock).toHaveBeenCalledTimes(1)
})

it('localiza el literal de un campo sin declarar equivalencia ni diferencia', async () => {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    if (String(input).includes('/cima-comparison')) return new Response(JSON.stringify([]))
    if (String(input).includes('/records/')) return new Response(JSON.stringify({
      id: 'record-1', entity_type: 'specialty', external_identifiers: [],
      blocks: [{ id: 'block-1', block_type: 'General', ordinal: 1, values: [
        { id: 'field-1', field_name: 'Descripción', source_column_index: 3, literal_value: 'Original', maintained_value: 'Valor exacto' },
      ] }],
    }))
    return new Response(JSON.stringify([{
      document_name: '51347', document_version_id: 'version-2', source_version: '2026-09',
      content_hash: 'a'.repeat(64), acquired_at: '2026-09-25T08:00:00Z',
      sections: [
        { locator: '1', literal_text: 'Aquí aparece Valor exacto.' },
        { locator: '2', literal_text: 'Otra información.' },
      ],
    }]))
  }))
  render(<CatalogCimaDocumentReader identityId='presentation-1' recordId='record-1' />)
  const selector = await screen.findByRole('combobox', { name: 'Localizar un valor de trabajo en la ficha' })
  fireEvent.change(selector, { target: { value: 'field-1' } })
  expect(screen.getByText('Valor buscado:')).toBeInTheDocument()
  expect(screen.getByText(/Una aparición no confirma equivalencia clínica/)).toBeInTheDocument()
  expect(screen.getAllByRole('link', { name: 'Apartado 1' })).toHaveLength(2)
})
