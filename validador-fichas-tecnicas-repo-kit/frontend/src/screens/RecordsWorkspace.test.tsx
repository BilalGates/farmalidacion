import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { clearRecordCache } from '../api/recordCache'
import { useRoute } from '../navigation'
import { RecordsWorkspace } from './RecordsWorkspace'

function Harness() {
  const route = useRoute()
  return <RecordsWorkspace recordId={route.name === 'ficha' ? route.id : undefined} />
}
function row(id: string) { return { id, display_name: `Registro ${id}`, identifier: id, origin: 'real', entity_type: 'medication', block_count: 0, field_count: 0, review_state: 'pendiente' } }
afterEach(() => { vi.unstubAllGlobals(); clearRecordCache(); localStorage.clear() })

it('mantiene filtros al seleccionar y cambia de ficha sin reutilizar el detalle anterior', async () => {
  window.location.hash = '#/fichas'
  let finish: ((value: Response) => void) | undefined
  const mock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    if (url.includes('/insights/records')) return new Response(JSON.stringify({ items: [row('uno'), row('dos')], total: 2, offset: 0, limit: 50 }))
    if (url.endsWith('/records/dos')) return new Promise<Response>(resolve => { finish = resolve })
    return new Response(JSON.stringify({ id: 'uno', entity_type: 'medication', blocks: [], external_identifiers: [] }))
  })
  vi.stubGlobal('fetch', mock)
  render(<Harness />)
  await screen.findByRole('button', { name: /Registro uno/ })
  fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'Registro' } })
  fireEvent.click(screen.getByRole('button', { name: 'Buscar' }))
  await waitFor(() => expect(mock.mock.calls.some(([url]) => String(url).includes('q=Registro'))).toBe(true))
  fireEvent.click(await screen.findByRole('button', { name: /Registro uno/ }))
  await screen.findByRole('heading', { name: 'Registro uno' })
  fireEvent.click(screen.getByRole('button', { name: /Registro dos/ }))
  await screen.findByText('Cargando ficha…')
  expect(screen.queryByRole('heading', { name: 'Registro uno' })).not.toBeInTheDocument()
  expect(screen.getByRole('searchbox', { name: /Buscar/ })).toHaveValue('Registro')
  expect(screen.getByLabelText('Estado de revisión')).toHaveValue('pendiente')
  await waitFor(() => expect(finish).toBeDefined())
  await act(async () => finish?.(new Response(JSON.stringify({ id: 'dos', entity_type: 'medication', blocks: [], external_identifiers: [] }))))
  await screen.findByRole('heading', { name: 'Registro dos' })
})

it('siguiente pendiente salta páginas vacías del filtro conservando la búsqueda', async () => {
  window.location.hash = '#/fichas/uno'
  const mock = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input))
    if (url.pathname === '/insights/records') {
      const offset = Number(url.searchParams.get('offset'))
      return new Response(JSON.stringify({ items: offset === 0 ? [row('uno')] : offset === 50 ? [] : [row('dos')], total: 101, offset, limit: 50 }))
    }
    return new Response(JSON.stringify({ id: url.pathname.endsWith('dos') ? 'dos' : 'uno', entity_type: 'medication', blocks: [], external_identifiers: [] }))
  })
  vi.stubGlobal('fetch', mock)
  render(<Harness />)
  await screen.findByRole('heading', { name: 'Registro uno' })
  fireEvent.click(screen.getByRole('button', { name: /Siguiente pendiente/ }))
  await screen.findByRole('heading', { name: 'Registro dos' })
  expect(mock.mock.calls.some(([url]) => String(url).includes('offset=50'))).toBe(true)
  expect(mock.mock.calls.some(([url]) => String(url).includes('offset=100'))).toBe(true)
  expect(window.location.hash).toBe('#/fichas/dos')
})
