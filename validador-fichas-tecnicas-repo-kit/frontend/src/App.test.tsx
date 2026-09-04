import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

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
  { identifier: 'ana', display_name: 'Ana Ruiz', assurance: 'declarada' },
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

    const query = new URL(url, 'http://localhost').searchParams.get('q')
    if (query) {
      const filtered = listPayload.items.filter((item) =>
        (item.display_name ?? '').toLowerCase().includes(query.toLowerCase()),
      )
      return ok({ items: filtered, total: filtered.length })
    }
    return ok(listPayload)
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
      candidate.querySelector('.field-row__name')?.textContent === fieldName,
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
  const select = await screen.findByRole('combobox', {
    name: 'Revisor que firma las decisiones',
  })
  await waitFor(() =>
    expect(within(select).getByRole('option', { name: 'Ana Ruiz' })).toBeDefined(),
  )
  await act(async () => {
    fireEvent.change(select, { target: { value: identifier } })
  })
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
  window.location.hash = '#/fichas'
  localStorage.clear()
  vi.stubGlobal('fetch', mockFetch())
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('Recorrido de la vertical de revisión', () => {
  it('muestra el aviso de datos DEMO y los módulos previstos en la navegación', async () => {
    render(<App />)

    expect(screen.getByText(/Datos de demostración/)).toBeVisible()
    expect(screen.getByRole('button', { name: /Revisión \(DEMO\)/ })).toBeVisible()
    // Un módulo no desarrollado se anuncia, no se oculta.
    expect(screen.getByRole('button', { name: /Validaciones\s*Pronto/ })).toBeVisible()
  })

  it('lista las fichas, filtra por búsqueda y abre el detalle', async () => {
    render(<App />)

    expect(await screen.findByText('Metotrexato 2,5 mg comprimidos')).toBeVisible()
    expect(screen.getByText('Omeprazol 20 mg cápsulas duras')).toBeVisible()

    await typeInto(screen.getByRole('searchbox', { name: /Buscar/ }), 'metotrexato')
    await waitFor(() =>
      expect(screen.queryByText('Omeprazol 20 mg cápsulas duras')).not.toBeInTheDocument(),
    )

    await click(screen.getAllByRole('button', { name: 'Abrir ficha' })[0])
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Metotrexato 2,5 mg comprimidos' }),
    ).toBeVisible()
  })

  it('muestra cada valor con su fuente y la discrepancia sin resolverla', async () => {
    render(<App />)
    await goTo('/fichas/rec-1')

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
    await goTo('/fichas/rec-1')
    await screen.findByRole('heading', { level: 1, name: 'Metotrexato 2,5 mg comprimidos' })

    await click(reviewButtonFor('CANTIDAD'))

    const select = screen.getByRole('combobox', { name: 'Decisión de revisión' })
    expect(select).toHaveValue('')
    expect(screen.getByRole('button', { name: 'Guardar decisión' })).toBeDisabled()
    expect(screen.getByText('Seleccione un revisor para poder firmar.')).toBeVisible()
    expect(postCount).toBe(0)
  })

  it('guarda una decisión firmada y vuelve al listado con el estado actualizado', async () => {
    render(<App />)

    await selectReviewer('ana')
    await goTo('/fichas/rec-1')
    await screen.findByRole('heading', { level: 1, name: 'Metotrexato 2,5 mg comprimidos' })

    await click(reviewButtonFor('CANTIDAD'))
    await selectOption(screen.getByRole('combobox', { name: 'Decisión de revisión' }), 'confirmado')
    await typeInto(screen.getByRole('textbox', { name: 'Valor final' }), '2,5 mg')
    await click(screen.getByRole('button', { name: 'Guardar decisión' }))

    expect(await screen.findByText('Decisión guardada.')).toBeVisible()
    expect(postCount).toBe(1)

    await click(screen.getByRole('button', { name: /Volver al listado/ }))
    const row = (await screen.findByText('Metotrexato 2,5 mg comprimidos')).closest('tr')
    expect(row).not.toBeNull()
    expect(within(row as HTMLElement).getByText('En revisión')).toBeVisible()
    expect(within(row as HTMLElement).getByText('1/3')).toBeVisible()
  })

  it('valida los requisitos de la decisión antes de enviarla', async () => {
    render(<App />)

    await selectReviewer('ana')
    await goTo('/fichas/rec-1')
    await screen.findByRole('heading', { level: 1, name: 'Metotrexato 2,5 mg comprimidos' })

    await click(reviewButtonFor('CANTIDAD'))
    await selectOption(screen.getByRole('combobox', { name: 'Decisión de revisión' }), 'no_aplica')

    expect(screen.getByRole('button', { name: 'Guardar decisión' })).toBeDisabled()
    expect(screen.getByText('«No aplica» exige un comentario.')).toBeVisible()
    expect(postCount).toBe(0)

    await typeInto(screen.getByRole('textbox', { name: 'Comentario de revisión' }), 'No corresponde')
    await click(screen.getByRole('button', { name: 'Guardar decisión' }))
    expect(await screen.findByText('Decisión guardada.')).toBeVisible()
    expect(postCount).toBe(1)
  })

  it('recuerda el revisor declarado entre montajes', async () => {
    const first = render(<App />)
    await selectReviewer('ana')
    expect(localStorage.getItem('farmalidacion.reviewer')).toBe('ana')
    first.unmount()

    render(<App />)
    expect(await screen.findByRole('combobox', { name: 'Revisor que firma las decisiones' })).toHaveValue('ana')
  })
})
