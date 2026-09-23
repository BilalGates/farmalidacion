import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { RealRecordListScreen } from './RealRecordListScreen'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

function cleanCatalogState() {
  window.sessionStorage.removeItem('farmalidacion.catalog-list-state')
}

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
  await screen.findByText('No hay identidades en este nivel')

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
  expect(screen.getByRole('region', { name: 'Tabla de registros; desplazamiento horizontal disponible' })).toHaveAttribute('tabindex', '0')
  expect(screen.getByRole('row', { name: /Medicamento de prueba/ })).toBeInTheDocument()
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

  const table = await screen.findByRole('region', { name: 'Tabla de registros; desplazamiento horizontal disponible' })
  table.scrollTop = 180
  table.scrollLeft = 42
  fireEvent.click(screen.getByRole('button', { name: 'Abrir expediente' }))

  expect(window.location.hash).toBe('#/catalogo/med-1')
  expect(JSON.parse(window.sessionStorage.getItem('farmalidacion.catalog-list-state') ?? '{}')).toMatchObject({
    entityType: null, offset: 0, tableScrollTop: 180, tableScrollLeft: 42,
  })
})

it('combina nivel y búsqueda sin descargar el catálogo al navegador', async () => {
  cleanCatalogState()
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(PAGE)))
  vi.stubGlobal('fetch', fetchMock)
  render(<RealRecordListScreen />)
  await screen.findByText('No hay identidades en este nivel')

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
  await screen.findByText('No hay identidades en este nivel')

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
  await screen.findByText('No hay identidades en este nivel')

  fireEvent.click(screen.getByRole('button', { name: 'Presentaciones' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
  fireEvent.click(screen.getByRole('button', { name: 'Genérico' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
  fireEvent.click(screen.getByRole('checkbox', { name: 'Huérfano' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4))

  expect(fetchMock.mock.calls[3][0]).toContain('commercial_class=generico')
  expect(fetchMock.mock.calls[3][0]).toContain('condition=huerfano')
})

it('permite combinar varias condiciones y limpiar todos los filtros', async () => {
  cleanCatalogState()
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(PAGE)))
  vi.stubGlobal('fetch', fetchMock)
  render(<RealRecordListScreen />)
  await screen.findByText('No hay identidades en este nivel')

  fireEvent.click(screen.getByRole('button', { name: 'Presentaciones' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
  fireEvent.click(screen.getByRole('checkbox', { name: 'Huérfano' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
  fireEvent.click(screen.getByRole('checkbox', { name: 'Control especial' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4))
  expect(fetchMock.mock.calls[3][0]).toContain('condition=huerfano')
  expect(fetchMock.mock.calls[3][0]).toContain('condition=especial_control_medico')

  fireEvent.click(screen.getByRole('button', { name: 'Limpiar filtros (3)' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(5))
  expect(fetchMock.mock.calls[4][0]).not.toContain('condition=')
  expect(fetchMock.mock.calls[4][0]).not.toContain('identity_type=')
})

it('limpia también una búsqueda escrita pero todavía no aplicada', async () => {
  cleanCatalogState()
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(PAGE)))
  vi.stubGlobal('fetch', fetchMock)
  render(<RealRecordListScreen />)
  await screen.findByText('No hay identidades en este nivel')

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
  await screen.findByText('No hay identidades en este nivel')
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
  await screen.findByText('No hay identidades en este nivel')

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
  await screen.findByText('No hay identidades en este nivel')

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
  await screen.findByText('No hay identidades en este nivel')

  fireEvent.click(screen.getByRole('button', { name: 'Genérico' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
  fireEvent.click(screen.getByRole('button', { name: 'DCP' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
  expect(fetchMock.mock.calls[2][0]).toContain('identity_type=dcp')
  expect(fetchMock.mock.calls[2][0]).not.toContain('commercial_class=')
})
