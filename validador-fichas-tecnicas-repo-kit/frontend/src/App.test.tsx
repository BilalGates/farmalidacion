import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { clearRecordCache } from './api/recordCache'
import { SessionContext } from './auth/SessionContext'

import { App } from './App'
import type { RecordList, Reviewer, TargetRecord } from './api/types'

/**
 * Pruebas del recorrido de la vertical: listado → búsqueda → ficha → revisión →
 * guardado → vuelta al listado con el estado actualizado.
 *
 * El backend se simula a nivel de `fetch` y no de los módulos de la aplicación:
 * así se ejercita el cliente HTTP real, que es donde vive el manejo de errores
 * de las barreras clínicas.
 *
 * Se usa `fireEvent` en lugar de `user-event`: la vertical no justifica añadir
 * una dependencia de pruebas, y las interacciones ejercitadas son clics,
 * escritura y selección simples.
 */

const REVIEWERS: Reviewer[] = [
  {
    identifier: 'ana',
    display_name: 'Ana Ruiz',
    assurance: 'declarada',
    role: 'farmaceutico',
    role_label: 'Farmacéutico',
    may_sign_pharmacist_states: true,
  },
]

function summary(overrides: Partial<RecordList['items'][number]> = {}) {
  return {
    id: 'rec-1',
    entity_type: 'medication',
    display_name: 'Metotrexato 2,5 mg comprimidos',
    active_ingredient: 'metotrexato',
    primary_identifier: 'DEMO-0002',
    block_count: 2,
    field_count: 3,
    pending_count: 3,
    resolved_count: 0,
    conflict_count: 1,
    review_state: 'requiere_revision' as const,
    last_reviewed_at: null,
    ...overrides,
  }
}

const OTHER = summary({
  id: 'rec-2',
  display_name: 'Omeprazol 20 mg cápsulas duras',
  active_ingredient: 'omeprazol',
  primary_identifier: 'DEMO-0001',
  conflict_count: 0,
  review_state: 'pendiente' as const,
})

const DETAIL: TargetRecord = {
  id: 'rec-1',
  entity_type: 'medication',
  external_identifiers: [
    { source_system: 'demo_showcase', source_identifier: 'DEMO-0002', source_version: 'demo-v1' },
  ],
  blocks: [
    {
      id: 'block-0',
      block_type: 'Medicamento - General',
      ordinal: 1,
      values: [
        {
          id: 'value-0',
          field_name: 'ME_DESCRIPCION',
          literal_value: 'Metotrexato 2,5 mg comprimidos',
          observed_type: 'CHAR(100)',
          logical_state: 'valued',
          provenance: [
            {
              source_fragment_id: 'frag-0',
              document_version_id: 'ver-1',
              locator_type: 'demo_locator',
              locator: 'maestro/DEMO-0002',
              literal_text: 'Fila de maestro',
              provenance_role: 'master_baseline',
            },
          ],
          validation_state: 'pendiente',
          conflict_status: 'consistent_pending_priority',
          has_conflict: false,
          history: [],
          prefill_policy: 'solo_evidencia' as const,
          prefill_presentation: 'casilla_vacia' as const,
          proposed_value: null,
          prefill_options: [],
          prefill_warning:
            'La ficha técnica no declara este dato. Este valor es criterio farmacéutico.',
        },
      ],
    },
    {
      id: 'block-1',
      block_type: 'Composición',
      ordinal: 1,
      values: [
        {
          id: 'value-1',
          field_name: 'CANTIDAD',
          literal_value: '2,5 mg',
          observed_type: 'CHAR(50)',
          logical_state: 'valued',
          provenance: [
            {
              source_fragment_id: 'frag-1',
              document_version_id: 'ver-1',
              locator_type: 'demo_locator',
              locator: 'maestro/DEMO-0002',
              literal_text: 'Fila de maestro',
              provenance_role: 'master_baseline',
            },
          ],
          validation_state: 'pendiente',
          conflict_status: 'unresolved_pending_priority',
          has_conflict: true,
          history: [],
          prefill_policy: 'solo_evidencia' as const,
          prefill_presentation: 'casilla_vacia' as const,
          proposed_value: null,
          prefill_options: [],
          prefill_warning:
            'La ficha técnica no declara este dato. Este valor es criterio farmacéutico.',
        },
        {
          id: 'value-2',
          field_name: 'CANTIDAD',
          literal_value: '2,5 mg/comprimido',
          observed_type: 'CHAR(50)',
          logical_state: 'valued',
          provenance: [
            {
              source_fragment_id: 'frag-2',
              document_version_id: 'ver-2',
              locator_type: 'demo_locator',
              locator: 'cima/DEMO-0002',
              literal_text: 'Metadato CIMA',
              provenance_role: 'cima_structured',
            },
          ],
          validation_state: 'pendiente',
          conflict_status: 'unresolved_pending_priority',
          has_conflict: true,
          history: [],
          prefill_policy: 'solo_evidencia' as const,
          prefill_presentation: 'casilla_vacia' as const,
          proposed_value: null,
          prefill_options: [],
          prefill_warning:
            'La ficha técnica no declara este dato. Este valor es criterio farmacéutico.',
        },
      ],
    },
  ],
}

let listPayload: RecordList
let postCount: number

function mockFetch() {
  return vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
    const url = String(input)
    const ok = (body: unknown) =>
      new Response(JSON.stringify(body), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })

    if (url.includes('/records/reviewers')) return ok(REVIEWERS)
    if (url.includes('/reviewers/roles')) return ok([{ value: 'farmaceutico', label: 'Farmacéutico' }])
    if (url.endsWith('/reviewers')) return ok(REVIEWERS.map(item => ({ ...item, active: true })))

    // El aviso de datos DEMO ya no está escrito en la interfaz: lo declara el
    // backend según la base que esté sirviendo. Esta suite ejercita la vertical
    // de revisión, que es DEMO por definición.
    if (url.includes('/database-info')) {
      return ok({
        mode: 'demo',
        backend: 'sqlite',
        database: 'demo',
        records_total: 2,
        records_real: 0,
        records_demo: 2,
        import_batches: 0,
        last_import_at: null,
        consistent: true,
      })
    }

    if (url.includes('/second-reviews')) return ok([])

    // La medición de tiempos también escribe: contarla como decisión haría que
    // estas pruebas dejasen de comprobar lo que dicen comprobar.
    if (url.includes('/timing/')) {
      return new Response(JSON.stringify({ id: 'sesion-1' }), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      })
    }

    if (init?.method === 'POST') {
      postCount += 1
      const body = JSON.parse(String(init.body)) as { state: string; comment: string | null }
      if (body.state === 'no_aplica' && !body.comment) {
        // Reproduce la barrera real de `validation_states`.
        return new Response(
          JSON.stringify({ detail: 'no_aplica exige comentario del farmacéutico.' }),
          { status: 400, headers: { 'Content-Type': 'application/json' } },
        )
      }
      listPayload = { items: [summary({ resolved_count: 1, review_state: 'en_revision' }), OTHER], total: 2 }
      return new Response(JSON.stringify({ sequence: 1 }), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      })
    }

    const detail = /\/records\/(rec-\d)$/.exec(url)
    if (detail) return ok(DETAIL)

    if (url.includes('/catalog/identities/')) {
      if (/\/(history|relations|classifications|cima-documents)$/.test(url)) return ok([])
      const record = listPayload.items.find((item) => url.endsWith(`/catalog/identities/${item.id}`))
      return ok({
        id: record?.id ?? 'rec-1', identity_type: 'dcp', code: record?.primary_identifier ?? null,
        display_name: record?.display_name ?? 'Metotrexato 2,5 mg comprimidos',
        target_record_id: null, source_system: 'demo', source_version: 'demo-v1',
        source_literal: record?.primary_identifier ?? null, active: true, version: 1,
      })
    }
    if (url.includes('/catalog/identities')) {
      const query = new URL(url).searchParams.get('q')?.toLowerCase()
      const items = listPayload.items
        .filter((item) => !query || (item.display_name ?? '').toLowerCase().includes(query))
        .map((item) => ({
          id: item.id, identity_type: 'dcp', code: item.primary_identifier,
          display_name: item.display_name, target_record_id: null,
          source_system: 'demo', source_version: 'demo-v1',
          source_workbook: 'medicamentos', source_literal: item.primary_identifier,
          active: true, version: 1,
        }))
      return ok({ items, total: items.length, limit: 50, offset: 0 })
    }

    // El listado único se sirve desde /insights/records, que pagina y devuelve
    // el origen y el estado de cada registro.
    const params = new URL(url, 'http://localhost').searchParams
    const query = params.get('q')
    const estado = params.get('estado')
    let items = listPayload.items.map((item) => ({
      id: item.id,
      entity_type: item.entity_type,
      origin: 'demo',
      display_name: item.display_name,
      identifier: item.primary_identifier,
      source_system: 'demo',
      block_count: item.block_count,
      field_count: item.field_count,
      review_state: item.review_state,
    }))
    if (query) {
      items = items.filter((item) =>
        (item.display_name ?? '').toLowerCase().includes(query.toLowerCase()),
      )
    }
    if (estado) items = items.filter((item) => item.review_state === estado)
    return ok({ items, total: items.length, limit: 50, offset: 0 })
  })
}


/** Navega disparando `hashchange`, que es lo que escucha `useRoute`. */
async function goTo(path: string) {
  await act(async () => {
    window.location.hash = path
    window.dispatchEvent(new HashChangeEvent('hashchange'))
  })
}

/** Botón «Revisar» del campo indicado, y no simplemente el primero.
 *
 * El nombre del campo aparece también en el resumen de discrepancias, que no es
 * una fila revisable; por eso se busca entre las filas de campo y no por texto.
 */
function reviewButtonFor(fieldName: string): HTMLElement {
  const rows = [...document.querySelectorAll('.field-row')] as HTMLElement[]
  const row = rows.find(
    (candidate) =>
      candidate.querySelector('.field-row__code')?.textContent === fieldName
      || candidate.querySelector('.field-row__name')?.textContent === fieldName,
  )
  if (!row) throw new Error(`No se encontró la fila del campo ${fieldName}`)
  return within(row).getByRole('button', { name: 'Revisar' })
}

/** Elige un revisor, esperando a que la lista configurable haya cargado.
 *
 * Sin la espera el `<option>` todavía no existe y la selección se descarta en
 * silencio, dejando la firma sin revisor.
 */
async function selectReviewer(identifier: string) {
  const original = window.location.hash.replace('#', '')
  await goTo('/revisores')
  if (screen.queryByRole('button', { name: 'Finalizar identificación' })) await click(screen.getByRole('button', { name: 'Finalizar identificación' }))
  if (identifier) {
    await waitFor(() => expect(screen.getByRole('option', { name: /Ana Ruiz/ })).toBeInTheDocument())
    await selectOption(screen.getByRole('combobox', { name: 'Revisor del piloto' }), identifier)
    await click(screen.getByRole('button', { name: 'Identificarse en el piloto' }))
  }
  await goTo(original)
}

async function click(element: HTMLElement) {
  await act(async () => {
    fireEvent.click(element)
  })
}

async function typeInto(element: HTMLElement, value: string) {
  await act(async () => {
    fireEvent.change(element, { target: { value } })
  })
}

async function selectOption(element: HTMLElement, value: string) {
  await act(async () => {
    fireEvent.change(element, { target: { value } })
  })
}

beforeEach(() => {
  listPayload = { items: [summary(), OTHER], total: 2 }
  postCount = 0
  // La vertical de revisión DEMO ya no es la pantalla de inicio: el inicio es
  // el panel de datos reales. Estas pruebas arrancan en su ruta propia.
  window.location.hash = '#/registros'
  window.sessionStorage.removeItem('farmalidacion.catalog-list-state')
  localStorage.clear()
  vi.stubGlobal('fetch', mockFetch())
})

afterEach(() => {
  // La caché es estado de módulo: sin limpiarla, una prueba serviría
  // la ficha que dejó la anterior.
  clearRecordCache()
  vi.unstubAllGlobals()
})

describe('Recorrido de la vertical de revisión', () => {
  it('da acceso a Datos y Exportaciones a quien sólo tiene permiso de exportación', async () => {
    const fetch = mockFetch()
    vi.stubGlobal('fetch', (input: string | URL | Request, init?: RequestInit) => String(input).endsWith('/exports') ? Promise.resolve(new Response('[]')) : fetch(input, init))
    window.location.hash = '#/revisores'
    render(<SessionContext.Provider value={{ subject_id: 'entra:test:ana', reviewer: REVIEWERS[0], capabilities: ['export.read', 'export.create'], logout: vi.fn() }}><App /></SessionContext.Provider>)
    expect(screen.queryByRole('button', { name: 'Catálogo' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Trabajo' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Revisores' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cerrar sesión' })).toBeEnabled()
    const team = await screen.findByRole('region', { name: 'Miembros del equipo' })
    expect(await within(team).findByRole('row', { name: /Ana Ruiz/ })).toBeInTheDocument()
    expect(within(team).queryByRole('button', { name: /Desactivar|Reactivar|Añadir/ })).not.toBeInTheDocument()
    await click(screen.getByRole('button', { name: 'Datos' }))
    expect(await screen.findByRole('heading', { name: 'Exportaciones' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Exportaciones' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Fuentes' })).not.toBeInTheDocument()
  })
  it('ofrece apariencia sólo en preferencias y filtra sin plegar la navegación', async () => {
    localStorage.setItem('farmalidacion.sidebar.collapsed', 'false')
    render(<App />)
    await screen.findByText('Metotrexato 2,5 mg comprimidos')
    expect(screen.queryByRole('combobox', { name: 'Tema visual' })).not.toBeInTheDocument()
    expect(screen.queryByRole('combobox', { name: 'Densidad de lectura' })).not.toBeInTheDocument()
    // Los filtros están siempre a la vista, encima de los resultados, y no pliegan la navegación.
    expect(screen.getByRole('region', { name: 'Buscar y filtrar el catálogo' })).toBeVisible()
    expect(screen.getByRole('combobox', { name: 'Libro de origen' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Plegar navegación' })).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('button', { name: 'Equipo y preferencias' })).toBeInTheDocument()
    await goTo('/revisores')
    expect(screen.getByRole('combobox', { name: 'Tema visual' })).toBeVisible()
    expect(screen.getByRole('combobox', { name: 'Densidad de lectura' })).toBeVisible()
  })

  it('finaliza la identificación declarada sin permitir cambios de identidad en cabecera', async () => {
    localStorage.setItem('farmalidacion.reviewer', 'ana')
    render(<App />)
    await waitFor(() => expect(screen.getByRole('button', { name: 'Identidad y acceso' })).toHaveTextContent('Ana Ruiz'))
    expect(screen.queryByRole('combobox', { name: 'Revisor que firma las decisiones' })).not.toBeInTheDocument()
    await goTo('/revisores')
    expect(screen.queryByRole('combobox', { name: 'Revisor del piloto' })).not.toBeInTheDocument()
    await click(screen.getByRole('button', { name: 'Finalizar identificación' }))
    expect(localStorage.getItem('farmalidacion.reviewer')).toBeNull()
    expect(screen.getByRole('button', { name: 'Identidad y acceso' })).toHaveTextContent('Sin identificar')
    expect(screen.getByRole('combobox', { name: 'Revisor del piloto' })).toBeVisible()
  })
  it('conserva ambas densidades sin modificar la elección de tema', async () => {
    window.location.hash = '#/revisores'
    const first = render(<App />)
    await selectOption(screen.getByRole('combobox', { name: 'Tema visual' }), 'dark')
    await selectOption(screen.getByRole('combobox', { name: 'Densidad de lectura' }), 'compact')
    expect(document.documentElement.dataset.density).toBe('compact')
    expect(document.documentElement.dataset.theme).toBe('dark')
    first.unmount()
    render(<App />)
    expect(screen.getByRole('combobox', { name: 'Densidad de lectura' })).toHaveValue('compact')
    expect(screen.getByRole('combobox', { name: 'Tema visual' })).toHaveValue('dark')
    await selectOption(screen.getByRole('combobox', { name: 'Densidad de lectura' }), 'comfortable')
    expect(document.documentElement.dataset.density).toBe('comfortable')
    expect(localStorage.getItem('farmalidacion.density')).toBe('comfortable')
    expect(localStorage.getItem('farmalidacion.theme')).toBe('dark')
  })

  it('recupera preferencias válidas cuando las guardadas son desconocidas', () => {
    window.location.hash = '#/revisores'
    localStorage.setItem('farmalidacion.density', 'unknown')
    localStorage.setItem('farmalidacion.theme', 'unknown')
    render(<App />)
    expect(screen.getByRole('combobox', { name: 'Densidad de lectura' })).toHaveValue('comfortable')
    expect(screen.getByRole('combobox', { name: 'Tema visual' })).toHaveValue('system')
  })
  it('permite escoger y conservar el modo oscuro', async () => {
    window.location.hash = '#/revisores'
    const first = render(<App />)
    await selectOption(screen.getByRole('combobox', { name: 'Tema visual' }), 'dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(localStorage.getItem('farmalidacion.theme')).toBe('dark')
    first.unmount()

    render(<App />)
    expect(screen.getByRole('combobox', { name: 'Tema visual' })).toHaveValue('dark')
    await selectOption(screen.getByRole('combobox', { name: 'Tema visual' }), 'light')
    expect(document.documentElement.dataset.theme).toBe('light')
  })

  it('sigue los cambios de preferencia del sistema cuando se selecciona automático', async () => {
    let changed: (() => void) | undefined
    let dark = false
    vi.stubGlobal('matchMedia', () => ({
      get matches() { return dark },
      addEventListener: (_: string, listener: () => void) => { changed = listener },
      removeEventListener: () => {},
    }))
    render(<App />)
    expect(document.documentElement.dataset.theme).toBe('light')
    dark = true
    act(() => changed?.())
    expect(document.documentElement.dataset.theme).toBe('dark')
    await goTo('/revisores')
    await selectOption(screen.getByRole('combobox', { name: 'Tema visual' }), 'light')
    expect(document.documentElement.dataset.theme).toBe('light')
  })

  it('muestra la navegación lateral y permite plegarla sin perder los destinos', async () => {
    localStorage.setItem('farmalidacion.sidebar.collapsed', 'true')
    render(<App />)

    expect(await screen.findByText('Última importación')).toBeVisible()
    expect(vi.mocked(fetch).mock.calls.some(([input]) => String(input).includes('/insights/dashboard'))).toBe(false)
    expect(await screen.findByLabelText('Base de datos de demostración')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Catálogo' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Datos' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Trabajo' })).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Exportaciones' })).not.toBeInTheDocument()
    const navigation = screen.getByRole('navigation', { name: 'Navegación principal' })
    expect(within(navigation).getByRole('button', { name: 'Catálogo' })).toHaveAttribute('aria-current', 'page')
    await click(screen.getByRole('button', { name: 'Expandir navegación' }))
    expect(screen.getByRole('button', { name: 'Plegar navegación' })).toHaveAttribute('aria-expanded', 'true')
    expect(localStorage.getItem('farmalidacion.sidebar.collapsed')).toBe('false')
    // Los módulos sin construir ya no se anuncian: un menú que promete lo que no
    // existe obliga a descubrir a base de clics qué es real.
    expect(screen.queryByRole('button', { name: /Historial \/ Auditoría/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Revisión \(DEMO\)/ })).toBeNull()
  })

  it('lista las fichas, filtra por búsqueda y abre el detalle', async () => {
    render(<App />)
    await goTo('/fichas')

    expect(await screen.findByText('Metotrexato 2,5 mg comprimidos')).toBeVisible()
    expect(screen.getByText('Omeprazol 20 mg cápsulas duras')).toBeVisible()

    await typeInto(screen.getByRole('searchbox', { name: /Buscar/ }), 'metotrexato')
    await click(screen.getByRole('button', { name: 'Buscar' }))
    await waitFor(() =>
      expect(screen.queryByText('Omeprazol 20 mg cápsulas duras')).not.toBeInTheDocument(),
    )

    await click(screen.getByRole('button', { name: 'Metotrexato 2,5 mg comprimidos' }))
    expect(screen.getByRole('dialog', { name: 'Expediente del registro' })).toBeVisible()
    expect(screen.getByRole('region', { name: 'Tabla de registros' })).toBeInTheDocument()
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Metotrexato 2,5 mg comprimidos' }),
    ).toBeVisible()
  })

  it('muestra cada valor con su fuente y la discrepancia sin resolverla', async () => {
    render(<App />)
    await goTo('/registros/rec-1')

    await screen.findByRole('heading', { level: 1, name: 'Metotrexato 2,5 mg comprimidos' })

    // Ambos valores en conflicto siguen visibles, cada uno con su fuente.
    // Aparecen dos veces cada uno: en el resumen de discrepancias y en su campo.
    expect(screen.getAllByText('2,5 mg', { exact: true }).length).toBe(2)
    expect(screen.getAllByText('2,5 mg/comprimido', { exact: true }).length).toBe(2)
    expect(screen.getAllByText('Maestro').length).toBeGreaterThan(0)
    expect(screen.getAllByText('CIMA').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Discrepancia detectada').length).toBeGreaterThan(0)

    // Nada afirma que la discrepancia esté resuelta.
    expect(
      screen.getByText(/Ninguna discrepancia se resuelve automáticamente/),
    ).toBeVisible()

    // La nota de hoja de ruta nombra la dependencia, no la da por cerrada.
    await click(screen.getByRole('button', { name: /Resolución de discrepancias/ }))
    expect(screen.getByText(/ADR-0007 aceptado/)).toBeVisible()

  })

  it('no permite firmar sin revisor y no preselecciona ninguna decisión', async () => {
    render(<App />)
    await goTo('/registros/rec-1')
    await screen.findByRole('heading', { level: 1, name: 'Metotrexato 2,5 mg comprimidos' })

    await click(reviewButtonFor('CANTIDAD'))

    expect(screen.getByRole('group', { name: 'Decisión de revisión' })).toBeVisible()
    expect(screen.queryByRole('radio', { checked: true })).toBeNull()
    expect(screen.getByRole('button', { name: 'Guardar decisión' })).toBeDisabled()
    expect(screen.getByText('Identifícate en Equipo y preferencias para poder firmar.')).toBeVisible()
    expect(postCount).toBe(0)
  })

  it('guarda una decisión firmada y vuelve al listado con el estado actualizado', async () => {
    render(<App />)

    await selectReviewer('ana')
    await goTo('/registros/rec-1')
    await screen.findByRole('heading', { level: 1, name: 'Metotrexato 2,5 mg comprimidos' })

    await click(reviewButtonFor('CANTIDAD'))
    await click(screen.getByRole('radio', { name: 'Validado' }))
    await typeInto(screen.getByRole('textbox', { name: 'Valor final' }), '2,5 mg')
    await click(screen.getByRole('button', { name: 'Guardar decisión' }))

    expect(await screen.findByText('Decisión guardada.')).toBeVisible()
    expect(postCount).toBe(1)

    await click(screen.getByRole('button', { name: /Volver al listado/ }))
    const row = (await screen.findByText('Metotrexato 2,5 mg comprimidos')).closest('tr')
    expect(row).not.toBeNull()
    expect(within(row as HTMLElement).getByText('Vigente')).toBeVisible()
  })

  it('valida los requisitos de la decisión antes de enviarla', async () => {
    render(<App />)

    await selectReviewer('ana')
    await goTo('/registros/rec-1')
    await screen.findByRole('heading', { level: 1, name: 'Metotrexato 2,5 mg comprimidos' })

    await click(reviewButtonFor('CANTIDAD'))
    await click(screen.getByRole('radio', { name: 'No aplica' }))

    expect(screen.getByRole('button', { name: 'Guardar decisión' })).toBeDisabled()
    expect(screen.getByText('«No aplica» exige un comentario.')).toBeVisible()
    expect(postCount).toBe(0)

    await typeInto(screen.getByRole('textbox', { name: 'Comentario de revisión' }), 'No corresponde')
    await click(screen.getByRole('button', { name: 'Guardar decisión' }))
    expect(await screen.findByText('Decisión guardada.')).toBeVisible()
    expect(postCount).toBe(1)
  })

  it('navega entre campos por teclado sin emitir decisiones', async () => {
    render(<App />)
    await goTo('/registros/rec-1')
    await screen.findByRole('heading', { level: 1, name: 'Metotrexato 2,5 mg comprimidos' })
    const rows = document.querySelectorAll<HTMLElement>('[data-review-field]')
    act(() => rows[0].focus())
    fireEvent.keyDown(rows[0], { key: 'ArrowDown', altKey: true })
    expect(rows[1]).toHaveFocus()
    expect(screen.getByRole('complementary', { name: 'Evidencia del campo activo' })).toHaveTextContent('CANTIDAD')
    expect(postCount).toBe(0)
  })

  it('recuerda el revisor declarado entre montajes', async () => {
    const first = render(<App />)
    await selectReviewer('ana')
    expect(localStorage.getItem('farmalidacion.reviewer')).toBe('ana')
    first.unmount()

    render(<App />)
    await waitFor(() => expect(screen.getByRole('button', { name: 'Identidad y acceso' })).toHaveTextContent('Ana Ruiz'))
  })
})
