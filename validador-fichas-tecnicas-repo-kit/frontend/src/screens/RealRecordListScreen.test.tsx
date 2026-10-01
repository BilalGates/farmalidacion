import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import { RealRecordListScreen } from './RealRecordListScreen'

vi.mock('./CatalogIdentityScreen', () => ({
  CatalogIdentityScreen: ({ identityId }: { identityId: string }) => <label>Edición {identityId}<input defaultValue={identityId} /></label>,
}))
beforeEach(() => {
  vi.spyOn(HTMLDialogElement.prototype, 'showModal').mockImplementation(function (this: HTMLDialogElement) { this.setAttribute('open', '') })
  vi.spyOn(HTMLDialogElement.prototype, 'close').mockImplementation(function (this: HTMLDialogElement) { this.removeAttribute('open') })
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

function cleanCatalogState() {
  window.sessionStorage.removeItem('farmalidacion.catalog-list-state')
}

it('añade a revisión desde una identidad vinculada sin escribir su identificador', async () => {
  cleanCatalogState()
  const page = {
    items: [{ id: 'identity-1', identity_type: 'dcp', code: '123', display_name: 'Medicamento vinculado',
      target_record_id: 'record-1', source_system: 'maestro', source_version: 'v1',
      source_workbook: 'medicamentos', source_literal: '123', active: true, version: 1 }],
    total: 1, limit: 50, offset: 0,
  }
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (url.includes('/catalog/identities')) return Promise.resolve(new Response(JSON.stringify(page)))
    if (url.endsWith('/queue') && init?.method === 'POST') return Promise.resolve(new Response(JSON.stringify({
      target_record_id: 'record-1', state: 'pendiente', version: 1, assignee_id: null,
      priority: 0, review_set: 'corpus', requires_second_review: false,
    })))
    return Promise.resolve(new Response(JSON.stringify([])))
  })
  vi.stubGlobal('fetch', fetchMock)
  render(<RealRecordListScreen />)
  fireEvent.click(await screen.findByRole('button', { name: '+ Revisar' }))
  await screen.findByText('Pendiente')
  expect(fetchMock.mock.calls.some(([url, init]) => String(url).endsWith('/queue') && init?.method === 'POST')).toBe(true)
})

it('filtra trabajo de revisión en el servidor sin cambiar de página', async () => {
  cleanCatalogState()
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(PAGE)))
  vi.stubGlobal('fetch', fetchMock)
  const originalHash = window.location.hash
  render(<RealRecordListScreen />)
  await screen.findByText('No hay identidades en el catálogo')
  fireEvent.click(screen.getByRole('button', { name: 'Pendientes' }))
  await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => String(url).includes('review_scope=pending'))).toBe(true))
  expect(window.location.hash).toBe(originalHash)
})

it('abre segundas validaciones sobre el catálogo sin subpáginas', async () => {
  cleanCatalogState()
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(PAGE))))
  render(<RealRecordListScreen />)
  await screen.findByText('No hay identidades en el catálogo')
  expect(screen.queryByRole('navigation', { name: 'Vistas del catálogo' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Segundas validaciones' }))
  expect(screen.getByRole('dialog', { name: 'Segundas validaciones' })).toBeInTheDocument()
})

const PAGE = {
  items: [],
  total: 0,
  limit: 50,
  offset: 0,
}

it('separa los niveles farmacéuticos del catálogo', async () => {
  cleanCatalogState()
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(PAGE)))
  vi.stubGlobal('fetch', fetchMock)
  render(<RealRecordListScreen />)
  await screen.findByText('No hay identidades en el catálogo')

  fireEvent.click(screen.getByRole('button', { name: 'Presentaciones' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
  expect(fetchMock.mock.calls[1][0]).toContain('identity_type=presentation')

  fireEvent.click(screen.getByRole('button', { name: 'DCP' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
  expect(fetchMock.mock.calls[2][0]).toContain('identity_type=dcp')

  fireEvent.click(screen.getByRole('button', { name: 'Sustancias activas' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4))
  expect(fetchMock.mock.calls[3][0]).toContain('identity_type=active_ingredient')
})

it('indica el tramo de resultados y permite recorrer la tabla con teclado', async () => {
  cleanCatalogState()
  const page = {
    items: [{
      id: 'med-52', identity_type: 'dcp', code: '654789', display_name: 'Medicamento de prueba',
      target_record_id: null, source_system: 'maestro', source_version: 'v1',
      source_workbook: 'medicamentos', source_literal: '654789', active: true, version: 1,
    }],
    total: 52,
    limit: 50,
    offset: 50,
  }
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(page)))
  vi.stubGlobal('fetch', fetchMock)
  window.sessionStorage.setItem('farmalidacion.catalog-list-state', JSON.stringify({
    term: '', query: '', offset: 50, entityType: 'dcp', showArchived: false,
    commercialClass: null, conditions: [],
  }))

  render(<RealRecordListScreen />)

  expect(await screen.findByText('Mostrando 51–51 · página 2 de 2')).toBeInTheDocument()
  const table = screen.getByRole('region', { name: 'Tabla de registros' })
  Object.defineProperty(table, 'scrollWidth', { configurable: true, value: 900 })
  Object.defineProperty(table, 'clientWidth', { configurable: true, value: 500 })
  fireEvent.resize(window)
  await waitFor(() => expect(screen.getByRole('region', { name: 'Tabla de registros; desplazamiento horizontal disponible' })).toHaveAttribute('tabindex', '0'))
  expect(screen.getByRole('row', { name: /Medicamento de prueba/ })).toBeInTheDocument()
})

it('evita una parada de teclado cuando la tabla no desborda', async () => {
  cleanCatalogState()
  const page = {
    items: [{ id: 'med-1', identity_type: 'dcp', code: '654789', display_name: 'Medicamento de prueba',
      target_record_id: null, source_system: 'maestro', source_version: 'v1',
      source_workbook: 'medicamentos', source_literal: '654789', active: true, version: 1 }],
    total: 1, limit: 50, offset: 0,
  }
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(page))))
  render(<RealRecordListScreen />)
  const table = await screen.findByRole('region', { name: 'Tabla de registros' })
  expect(table).not.toHaveAttribute('tabindex')
})

it('guarda filtros y posición de lectura al abrir un expediente', async () => {
  cleanCatalogState()
  const page = {
    items: [{
      id: 'med-1', identity_type: 'dcp', code: '654789', display_name: 'Medicamento de prueba',
      target_record_id: null, source_system: 'maestro', source_version: 'v1',
      source_workbook: 'medicamentos', source_literal: '654789', active: true, version: 1,
    }],
    total: 1,
    limit: 50,
    offset: 0,
  }
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(page)))
  vi.stubGlobal('fetch', fetchMock)
  vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined)
  render(<RealRecordListScreen />)

  const table = await screen.findByRole('region', { name: 'Tabla de registros' })
  table.scrollTop = 180
  table.scrollLeft = 42
  fireEvent.click(screen.getByRole('button', { name: 'Abrir expediente' }))

  expect(screen.getByRole('dialog', { name: 'Expediente del registro' })).toBeInTheDocument()
  expect(screen.getByRole('region', { name: 'Tabla de registros' })).toBeInTheDocument()
  expect(JSON.parse(window.sessionStorage.getItem('farmalidacion.catalog-list-state') ?? '{}')).toMatchObject({
    entityType: null, offset: 0, tableScrollTop: 180, tableScrollLeft: 42,
  })
})

it('combina nivel y búsqueda sin descargar el catálogo al navegador', async () => {
  cleanCatalogState()
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(PAGE)))
  vi.stubGlobal('fetch', fetchMock)
  render(<RealRecordListScreen />)
  await screen.findByText('No hay identidades en el catálogo')

  fireEvent.click(screen.getByRole('button', { name: 'Presentaciones' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
  fireEvent.change(screen.getByRole('searchbox'), { target: { value: '654789' } })
  fireEvent.click(screen.getByRole('button', { name: 'Buscar' }))

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
  expect(fetchMock.mock.calls[2][0]).toContain('identity_type=presentation')
  expect(fetchMock.mock.calls[2][0]).toContain('q=654789')
})

it('ordena el catálogo desde el servidor sin ordenar sólo la página visible', async () => {
  cleanCatalogState()
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(PAGE)))
  vi.stubGlobal('fetch', fetchMock)
  render(<RealRecordListScreen />)
  await screen.findByText('No hay identidades en el catálogo')

  fireEvent.change(screen.getByRole('combobox', { name: 'Ordenar por' }), { target: { value: 'code_desc' } })
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
  expect(fetchMock.mock.calls[1][0]).toContain('sort_by=code_desc')
  expect(fetchMock.mock.calls[1][0]).toContain('limit=50')
  expect(fetchMock.mock.calls[1][0]).toContain('offset=0')
})

it('combina clase comercial y condición como filtros del servidor', async () => {
  cleanCatalogState()
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(PAGE)))
  vi.stubGlobal('fetch', fetchMock)
  render(<RealRecordListScreen />)
  await screen.findByText('No hay identidades en el catálogo')

  fireEvent.click(screen.getByRole('button', { name: 'Presentaciones' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
  fireEvent.click(screen.getByRole('button', { name: 'Genérico' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
  fireEvent.click(screen.getByRole('checkbox', { name: 'Huérfano' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4))

  expect(fetchMock.mock.calls[3][0]).toContain('commercial_class=generico')
  expect(fetchMock.mock.calls[3][0]).toContain('condition=huerfano')
})

it('explica el vacío provocado por filtros y permite recuperar el catálogo completo', async () => {
  cleanCatalogState()
  const fetchMock = vi.fn().mockImplementation(async () => new Response(JSON.stringify(PAGE)))
  vi.stubGlobal('fetch', fetchMock)
  render(<RealRecordListScreen />)
  await screen.findByText('No hay identidades en el catálogo')
  fireEvent.click(screen.getByRole('button', { name: 'Presentaciones' }))
  expect(await screen.findByText('No hay resultados con estos filtros')).toBeInTheDocument()
  fireEvent.click(screen.getAllByRole('button', { name: 'Limpiar filtros' }).at(-1)!)
  expect(await screen.findByText('No hay identidades en el catálogo')).toBeInTheDocument()
})

it('permite combinar varias condiciones y limpiar todos los filtros', async () => {
  cleanCatalogState()
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(PAGE)))
  vi.stubGlobal('fetch', fetchMock)
  render(<RealRecordListScreen />)
  await screen.findByText('No hay identidades en el catálogo')

  fireEvent.click(screen.getByRole('button', { name: 'Presentaciones' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
  fireEvent.click(screen.getByRole('checkbox', { name: 'Huérfano' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
  fireEvent.click(screen.getByRole('checkbox', { name: 'Control especial' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4))
  expect(fetchMock.mock.calls[3][0]).toContain('condition=huerfano')
  expect(fetchMock.mock.calls[3][0]).toContain('condition=especial_control_medico')

  fireEvent.click(screen.getByRole('button', { name: 'Condición: Huérfano ×' }))
  await waitFor(() => expect(screen.getByLabelText('Resultados del catálogo')).toHaveFocus())
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(5))

  fireEvent.click(screen.getByRole('button', { name: 'Limpiar filtros · 2' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(6))
  expect(fetchMock.mock.calls[5][0]).not.toContain('condition=')
  expect(fetchMock.mock.calls[5][0]).not.toContain('identity_type=')
})

it('limpia también una búsqueda escrita pero todavía no aplicada', async () => {
  cleanCatalogState()
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(PAGE)))
  vi.stubGlobal('fetch', fetchMock)
  render(<RealRecordListScreen />)
  await screen.findByText('No hay identidades en el catálogo')

  fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'texto pendiente' } })
  fireEvent.click(screen.getByRole('button', { name: 'Limpiar filtros' }))
  expect(screen.getByRole('searchbox')).toHaveValue('')
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
})

it('restaura filtros al volver a montar el listado', async () => {
  cleanCatalogState()
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(PAGE)))
  vi.stubGlobal('fetch', fetchMock)
  const first = render(<RealRecordListScreen />)
  await screen.findByText('No hay identidades en el catálogo')
  fireEvent.click(screen.getByRole('button', { name: 'Presentaciones' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
  fireEvent.click(screen.getByRole('checkbox', { name: 'Huérfano' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
  first.unmount()

  render(<RealRecordListScreen />)
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4))
  expect(fetchMock.mock.calls[3][0]).toContain('identity_type=presentation')
  expect(fetchMock.mock.calls[3][0]).toContain('condition=huerfano')
})

it('recupera una página guardada que ya queda fuera del total actual', async () => {
  cleanCatalogState()
  window.sessionStorage.setItem('farmalidacion.catalog-list-state', JSON.stringify({
    term: '', query: '', offset: 100, entityType: 'presentation', showArchived: false,
    commercialClass: null, conditions: [],
  }))
  const stalePage = { ...PAGE, total: 80, offset: 100 }
  const validPage = { ...PAGE, total: 80, offset: 50 }
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(new Response(JSON.stringify(stalePage)))
    .mockResolvedValueOnce(new Response(JSON.stringify(validPage)))
  vi.stubGlobal('fetch', fetchMock)

  render(<RealRecordListScreen />)
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
  expect(fetchMock.mock.calls[0][0]).toContain('offset=100')
  expect(fetchMock.mock.calls[1][0]).toContain('offset=50')
})

it('al elegir una condición desde Todo el catálogo conserva el contexto de presentaciones', async () => {
  cleanCatalogState()
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(PAGE)))
  vi.stubGlobal('fetch', fetchMock)
  render(<RealRecordListScreen />)
  await screen.findByText('No hay identidades en el catálogo')

  fireEvent.click(screen.getByRole('checkbox', { name: 'Huérfano' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
  expect(fetchMock.mock.calls[1][0]).toContain('identity_type=presentation')
  expect(screen.getByRole('group', { name: 'Clase comercial' })).toBeInTheDocument()
})

it('separa las vistas por los tres libros Excel originales', async () => {
  cleanCatalogState()
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(PAGE)))
  vi.stubGlobal('fetch', fetchMock)
  render(<RealRecordListScreen />)
  await screen.findByText('No hay identidades en el catálogo')

  fireEvent.click(screen.getByRole('button', { name: 'Especialidades · CN' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
  expect(fetchMock.mock.calls[1][0]).toContain('source_workbook=especialidades')
  expect(fetchMock.mock.calls[1][0]).toContain('identity_type=presentation')

  fireEvent.click(screen.getByRole('button', { name: 'Medicamentos · DCP' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
  expect(fetchMock.mock.calls[2][0]).toContain('source_workbook=medicamentos')
  expect(fetchMock.mock.calls[2][0]).toContain('identity_type=dcp')

  fireEvent.click(screen.getByRole('button', { name: 'Principios activos · PA' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4))
  expect(fetchMock.mock.calls[3][0]).toContain('source_workbook=principios_activos')
  expect(fetchMock.mock.calls[3][0]).toContain('identity_type=active_ingredient')
})

it('retira filtros de presentación cuando se cambia a medicamentos', async () => {
  cleanCatalogState()
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(PAGE)))
  vi.stubGlobal('fetch', fetchMock)
  render(<RealRecordListScreen />)
  await screen.findByText('No hay identidades en el catálogo')

  fireEvent.click(screen.getByRole('button', { name: 'Genérico' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
  fireEvent.click(screen.getByRole('button', { name: 'DCP' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
  expect(fetchMock.mock.calls[2][0]).toContain('identity_type=dcp')
  expect(fetchMock.mock.calls[2][0]).not.toContain('commercial_class=')
})


it('recorre registros entre páginas, conserva filtros y recupera ediciones al volver', async () => {
  cleanCatalogState()
  const item = (id: string) => ({ id, identity_type: 'dcp', code: id, display_name: id,
    target_record_id: null, source_system: 'maestro', source_version: 'v1', active: true, version: 1 })
  const first = { items: Array.from({ length: 50 }, (_, i) => item(`med-${i}`)), total: 51, limit: 50, offset: 0 }
  const last = { items: [item('med-50')], total: 51, limit: 50, offset: 50 }
  const fetchMock = vi.fn().mockImplementation((url: string) => Promise.resolve(new Response(JSON.stringify(url.includes('offset=50') ? last : first))))
  vi.stubGlobal('fetch', fetchMock)
  render(<RealRecordListScreen />)
  await screen.findByText('med-49', { selector: '.catalog-row__name' })
  fireEvent.click(screen.getAllByRole('button', { name: 'Abrir expediente' })[49])
  fireEvent.change(screen.getByRole('textbox', { name: 'Edición med-49' }), { target: { value: 'Borrador conservado' } })
  fireEvent.click(screen.getByRole('button', { name: 'Siguiente registro →' }))
  expect(await screen.findByRole('textbox', { name: 'Edición med-50' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Siguiente registro →' })).toBeDisabled()
  expect(fetchMock.mock.calls.some(([url]) => url.includes('offset=50') && url.includes('sort_by=name_asc'))).toBe(true)
  fireEvent.click(screen.getByRole('button', { name: '← Anterior registro' }))
  await waitFor(() => expect(screen.getByRole('textbox', { name: 'Edición med-49' })).toHaveValue('Borrador conservado'))
  fireEvent.click(screen.getByRole('button', { name: 'Cerrar' }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  fireEvent.click(screen.getAllByRole('button', { name: 'Abrir expediente' })[49])
  expect(screen.getByRole('textbox', { name: 'Edición med-49' })).toHaveValue('Borrador conservado')
})

it('mantiene el expediente abierto si falla el avance y permite cerrar con Escape', async () => {
  cleanCatalogState()
  const page = { items: [{ id: 'med-1', identity_type: 'dcp', code: '1', display_name: 'Prueba', target_record_id: null, active: true }], total: 51, limit: 50, offset: 0 }
  vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(new Response(JSON.stringify(page))).mockRejectedValue(new Error('Sin conexión')))
  render(<RealRecordListScreen />)
  fireEvent.click(await screen.findByRole('button', { name: 'Abrir expediente' }))
  fireEvent.click(screen.getByRole('button', { name: 'Siguiente registro →' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('No se ha podido contactar con el servidor.')
  expect(screen.getByRole('textbox', { name: 'Edición med-1' })).toBeInTheDocument()
  fireEvent(screen.getByRole('dialog'), new Event('cancel', { cancelable: true }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})
