import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { clearRecordCache } from '../api/recordCache'

import type { TargetRecord } from '../api/types'
import { ReviewScreen } from './ReviewScreen'

/**
 * Pruebas de la pantalla canónica de revisión (DEV-503 / DEV-504).
 *
 * Lo que se comprueba aquí no es que la pantalla dibuje: es que la navegación
 * por teclado mueva el foco sin decidir nada, que ningún atajo firme una
 * decisión incompleta y que la evidencia mostrada sea la del campo activo.
 */

const REVIEWER = {
  identifier: 'ana',
  display_name: 'Ana',
  assurance: 'declarada' as const,
  role: 'farmaceutico' as const,
  role_label: 'Farmacéutico',
  may_sign_pharmacist_states: true,
}

function record(): TargetRecord {
  return {
    id: 'rec-1',
    entity_type: 'specialty',
    external_identifiers: [],
    blocks: [
      {
        id: 'block-1',
        block_type: 'specialty_general',
        ordinal: 1,
        values: [
          {
            id: 'value-1',
            field_name: 'DESCRIPCION',
            literal_value: 'Omeprazol 20 mg',
            observed_type: 'text',
            logical_state: 'valued',
            validation_state: 'pendiente' as const,
            conflict_status: 'single_source',
            has_conflict: false,
            history: [],
            prefill_policy: 'solo_evidencia' as const,
            prefill_presentation: 'casilla_vacia' as const,
            proposed_value: null,
            prefill_options: [],
            prefill_warning:
              'La ficha técnica no declara este dato. Este valor es criterio farmacéutico.',
            provenance: [
              {
                source_fragment_id: 'frag-1',
                document_version_id: 'ver-1',
                locator_type: 'excel_row',
                locator: '{"row":10,"sheet":"General"}',
                literal_text: 'Texto literal del maestro.',
                provenance_role: 'master_baseline',
              },
            ],
          },
          {
            id: 'value-2',
            field_name: 'CODIGO_NACIONAL',
            literal_value: '707703',
            observed_type: 'text',
            logical_state: 'valued',
            validation_state: 'pendiente' as const,
            conflict_status: 'single_source',
            has_conflict: false,
            history: [],
            prefill_policy: 'solo_evidencia' as const,
            prefill_presentation: 'casilla_vacia' as const,
            proposed_value: null,
            prefill_options: [],
            prefill_warning:
              'La ficha técnica no declara este dato. Este valor es criterio farmacéutico.',
            provenance: [
              {
                source_fragment_id: 'frag-2',
                document_version_id: 'ver-1',
                locator_type: 'excel_row',
                locator: '{"row":11,"sheet":"General"}',
                literal_text: 'Otro fragmento distinto.',
                provenance_role: 'master_baseline',
              },
            ],
          },
        ],
      },
      {
        id: 'block-2',
        block_type: 'specialty_excipient',
        ordinal: 1,
        values: [],
      },
    ],
  }
}

function stubFetch(...responses: unknown[]) {
  const mock = vi.fn()
  for (const body of responses) {
    mock.mockResolvedValueOnce({ ok: true, status: 200, json: async () => body } as Response)
  }
  mock.mockResolvedValue({ ok: true, status: 200, json: async () => record() } as Response)
  vi.stubGlobal('fetch', mock)
  return mock
}


/**
 * Enruta la respuesta por URL en lugar de por orden de llamada.
 *
 * La pantalla pide la ficha y abre una sesión de medición; encadenar respuestas
 * por orden haría que añadir una petición rompiera pruebas que no la miran.
 */
function routeFetch(options: {
  record?: unknown
  decision?: { ok: boolean; status: number; body: unknown }
  afterDecision?: unknown
}) {
  let decided = false
  const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (url.includes('/timing/')) {
      return { ok: true, status: 201, json: async () => ({ id: 'sesion-1' }) } as Response
    }
    if (init?.method === 'POST' && url.includes('/decisions')) {
      decided = true
      const outcome = options.decision ?? { ok: true, status: 201, body: {} }
      return {
        ok: outcome.ok,
        status: outcome.status,
        json: async () => outcome.body,
      } as Response
    }
    const body = decided && options.afterDecision ? options.afterDecision : options.record
    return { ok: true, status: 200, json: async () => body ?? record() } as Response
  })
  vi.stubGlobal('fetch', mock)
  return mock
}

afterEach(() => {
  // La caché es estado de módulo: sin limpiarla, una prueba serviría
  // la ficha que dejó la anterior.
  clearRecordCache()
  vi.unstubAllGlobals()
  window.localStorage.clear()
})

it('en compacto abre un solo editor y conserva borradores al filtrar', async () => {
  routeFetch({})
  render(<ReviewScreen recordId='rec-1' reviewer={REVIEWER} compact />)
  await screen.findByRole('heading', { name: 'Omeprazol 20 mg' })
  fireEvent.click(screen.getAllByRole('button', { name: 'Revisar' })[0])
  fireEvent.change(screen.getByLabelText('Decisión de revisión'), { target: { value: 'corregido' } })
  fireEvent.change(screen.getByLabelText('Valor final'), { target: { value: 'borrador explícito' } })
  fireEvent.click(screen.getByRole('button', { name: 'Revisar' }))
  expect(screen.getAllByLabelText('Decisión de revisión')).toHaveLength(1)
  expect(screen.getByLabelText('Decisión de revisión')).toHaveValue('')
  fireEvent.change(screen.getByLabelText('Localizar campo'), { target: { value: 'descripción' } })
  expect(screen.getByRole('complementary', { name: 'Evidencia del campo activo' })).toHaveTextContent('Texto literal del maestro.')
  fireEvent.click(screen.getByRole('button', { name: 'Revisar' }))
  expect(screen.getByLabelText('Valor final')).toHaveValue('borrador explícito')
})

it('guardar y siguiente campo solo avanza tras confirmación del backend', async () => {
  const saved = record()
  saved.blocks[0].values[0].validation_state = 'confirmado'
  saved.blocks[0].values[0].history = [{ sequence: 1, state: 'confirmado', final_value: 'dato revisado', comment: null, reviewer_id: 'ana', reviewer_assurance: 'declarada', decided_at: '2026-09-10T09:00:00Z' }]
  routeFetch({ afterDecision: saved })
  render(<ReviewScreen recordId='rec-1' reviewer={REVIEWER} compact />)
  await screen.findByRole('heading', { name: 'Omeprazol 20 mg' })
  fireEvent.click(screen.getAllByRole('button', { name: 'Revisar' })[0])
  fireEvent.change(screen.getByLabelText('Decisión de revisión'), { target: { value: 'confirmado' } })
  expect(screen.getByLabelText('Valor final')).toHaveValue('')
  fireEvent.change(screen.getByLabelText('Valor final'), { target: { value: 'dato revisado' } })
  fireEvent.click(screen.getByRole('button', { name: 'Guardar y siguiente campo' }))
  await screen.findByText('Decisión guardada.')
  await waitFor(() => expect(document.querySelector('[data-review-field="value-2"] button[aria-expanded="true"]')).not.toBeNull())
  expect(localStorage.getItem('farmalidacion.draft.rec-1.value-1')).toBeNull()
})

it('un rechazo de guardar y avanzar conserva el campo y el borrador', async () => {
  routeFetch({ decision: { ok: false, status: 409, body: { detail: 'Revisión rechazada.' } } })
  render(<ReviewScreen recordId='rec-1' reviewer={REVIEWER} compact />)
  await screen.findByRole('heading', { name: 'Omeprazol 20 mg' })
  fireEvent.click(screen.getAllByRole('button', { name: 'Revisar' })[0])
  fireEvent.change(screen.getByLabelText('Decisión de revisión'), { target: { value: 'confirmado' } })
  fireEvent.change(screen.getByLabelText('Valor final'), { target: { value: 'mi borrador' } })
  fireEvent.click(screen.getByRole('button', { name: 'Guardar y siguiente campo' }))
  await screen.findByText('Revisión rechazada.')
  expect(screen.getByLabelText('Valor final')).toHaveValue('mi borrador')
  expect(document.querySelector('[data-review-field="value-1"] button[aria-expanded="true"]')).not.toBeNull()
})

it('bloquea la edición mientras se guarda para no descartar cambios escritos durante la petición', async () => {
  let finish: ((response: Response) => void) | undefined
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    if (String(input).includes('/decisions') && init?.method === 'POST') return new Promise<Response>(resolve => { finish = resolve })
    return new Response(JSON.stringify(String(input).includes('/timing/') ? { id: 'sesion' } : record()))
  }))
  render(<ReviewScreen recordId='rec-1' reviewer={REVIEWER} compact />)
  await screen.findByRole('heading', { name: 'Omeprazol 20 mg' })
  fireEvent.click(screen.getAllByRole('button', { name: 'Revisar' })[0])
  fireEvent.change(screen.getByLabelText('Decisión de revisión'), { target: { value: 'confirmado' } })
  fireEvent.change(screen.getByLabelText('Valor final'), { target: { value: 'valor enviado' } })
  fireEvent.click(screen.getByRole('button', { name: 'Guardar decisión' }))
  await waitFor(() => expect(finish).toBeDefined())
  expect(screen.getByLabelText('Decisión de revisión')).toBeDisabled()
  expect(screen.getByLabelText('Valor final')).toBeDisabled()
  expect(screen.getByLabelText('Comentario de revisión')).toBeDisabled()
  await act(async () => finish?.(new Response(JSON.stringify({ detail: 'Rechazado' }), { status: 409 })))
  await screen.findByText('Rechazado')
  expect(screen.getByLabelText('Valor final')).toBeEnabled()
  expect(screen.getByLabelText('Valor final')).toHaveValue('valor enviado')
})

it('presenta las tres zonas con la evidencia del campo activo', async () => {
  stubFetch(record())
  render(<ReviewScreen recordId='rec-1' reviewer={REVIEWER} />)

  await screen.findByRole('heading', { level: 1, name: 'Omeprazol 20 mg' })
  expect(screen.getByLabelText('Campos del registro')).toBeInTheDocument()
  expect(screen.getByText('Libro Especialidades · hoja General')).toBeInTheDocument()
  expect(screen.getByRole('heading', { level: 2, name: 'Datos generales' })).toBeInTheDocument()
  expect(screen.getByText('Libro Especialidades · hoja Excipientes')).toBeInTheDocument()

  const evidence = screen.getByRole('complementary', { name: 'Evidencia del campo activo' })
  expect(within(evidence).getByText('Texto literal del maestro.')).toBeInTheDocument()
  expect(screen.getByText('0 de 2 campos revisados')).toBeInTheDocument()
})

it('permite mantener campos de registros fuente sin identidad canónica ni decisión farmacéutica', async () => {
  const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (url.includes('/timing/')) {
      return { ok: true, status: 201, json: async () => ({ id: 'sesion-1' }) } as Response
    }
    if (init?.method === 'POST' && url.includes('/maintenance')) {
      return { ok: true, status: 201, json: async () => ({ sequence: 1 }) } as Response
    }
    return { ok: true, status: 200, json: async () => record() } as Response
  })
  vi.stubGlobal('fetch', mock)
  render(<ReviewScreen recordId='rec-1' reviewer={REVIEWER} />)

  await screen.findByRole('heading', { level: 1, name: 'Omeprazol 20 mg' })
  fireEvent.click(screen.getByText('Mantenimiento del libro original · editar datos importados'))
  await screen.findByRole('heading', { level: 2, name: 'Campos importados' })
  fireEvent.click(screen.getAllByRole('button', { name: 'Editar campo' })[0])
  fireEvent.change(screen.getByLabelText('Nuevo valor para DESCRIPCION'), {
    target: { value: 'Omeprazol 20 mg corregido' },
  })
  fireEvent.change(screen.getByLabelText('Motivo'), { target: { value: 'Corrección de prueba' } })
  fireEvent.click(screen.getByRole('button', { name: 'Guardar' }))

  await waitFor(() => expect(mock.mock.calls.some(([url, init]) =>
    String(url).includes('/records/values/value-1/maintenance') && init?.method === 'POST',
  )).toBe(true))
  expect(mock.mock.calls.some(([url]) => String(url).includes('/decisions'))).toBe(false)
  const maintenanceCall = mock.mock.calls.find(([url, init]) =>
    String(url).includes('/records/values/value-1/maintenance') && init?.method === 'POST',
  )
  expect(JSON.parse(String(maintenanceCall?.[1]?.body))).toMatchObject({
    expected_sequence: 0,
    value: 'Omeprazol 20 mg corregido',
    actor_id: 'ana',
    reason: 'Corrección de prueba',
  })
})

it('Alt+flechas mueve el foco entre campos sin guardar nada', async () => {
  const fetchMock = stubFetch(record())
  render(<ReviewScreen recordId='rec-1' reviewer={REVIEWER} />)
  await screen.findByRole('heading', { level: 1, name: 'Omeprazol 20 mg' })

  const rows = document.querySelectorAll<HTMLElement>('[data-review-field]')
  rows[0].focus()
  const workspace = document.querySelector('.review-workspace') as HTMLElement

  fireEvent.keyDown(workspace, { key: 'ArrowDown', altKey: true })
  await waitFor(() => expect(document.activeElement).toBe(rows[1]))

  fireEvent.keyDown(workspace, { key: 'ArrowUp', altKey: true })
  await waitFor(() => expect(document.activeElement).toBe(rows[0]))

  // Navegar no escribe: sólo se ha pedido la ficha.
  expect(fetchMock.mock.calls.filter(
      ([url, init]) => init?.method === 'POST' && String(url).includes('/decisions'),
    )).toHaveLength(0)
})

it('la evidencia sigue al campo que recibe el foco', async () => {
  stubFetch(record())
  render(<ReviewScreen recordId='rec-1' reviewer={REVIEWER} />)
  await screen.findByRole('heading', { level: 1, name: 'Omeprazol 20 mg' })

  const rows = document.querySelectorAll<HTMLElement>('[data-review-field]')
  fireEvent.focus(rows[1])

  const evidence = screen.getByRole('complementary', { name: 'Evidencia del campo activo' })
  await waitFor(() =>
    expect(within(evidence).getByText('Otro fragmento distinto.')).toBeInTheDocument(),
  )
  expect(within(evidence).queryByText('Texto literal del maestro.')).not.toBeInTheDocument()
})

it('Alt+E lleva a la evidencia y Alt+C devuelve al campo', async () => {
  stubFetch(record())
  render(<ReviewScreen recordId='rec-1' reviewer={REVIEWER} />)
  await screen.findByRole('heading', { level: 1, name: 'Omeprazol 20 mg' })

  const rows = document.querySelectorAll<HTMLElement>('[data-review-field]')
  rows[0].focus()
  const workspace = document.querySelector('.review-workspace') as HTMLElement
  const evidence = screen.getByRole('complementary', { name: 'Evidencia del campo activo' })

  fireEvent.keyDown(workspace, { key: 'e', altKey: true })
  await waitFor(() => expect(document.activeElement).toBe(evidence))

  fireEvent.keyDown(workspace, { key: 'c', altKey: true })
  await waitFor(() => expect(document.activeElement).toBe(rows[0]))
})

it('Ctrl+Enter no guarda una decisión incompleta', async () => {
  const fetchMock = stubFetch(record())
  render(<ReviewScreen recordId='rec-1' reviewer={REVIEWER} />)
  await screen.findByRole('heading', { level: 1, name: 'Omeprazol 20 mg' })

  fireEvent.click(screen.getAllByRole('button', { name: 'Revisar' })[0])

  // Sin decisión elegida, el atajo no puede firmar por el revisor.
  fireEvent.keyDown(screen.getByLabelText('Decisión de revisión'), {
    key: 'Enter',
    ctrlKey: true,
  })
  expect(fetchMock.mock.calls.filter(
      ([url, init]) => init?.method === 'POST' && String(url).includes('/decisions'),
    )).toHaveLength(0)
})

it('Ctrl+Enter guarda cuando la decisión ya es admisible', async () => {
  const fetchMock = stubFetch(record())
  render(<ReviewScreen recordId='rec-1' reviewer={REVIEWER} />)
  await screen.findByRole('heading', { level: 1, name: 'Omeprazol 20 mg' })

  fireEvent.click(screen.getAllByRole('button', { name: 'Revisar' })[0])
  fireEvent.change(screen.getByLabelText('Decisión de revisión'), {
    target: { value: 'confirmado' },
  })
  fireEvent.change(screen.getByLabelText('Valor final'), { target: { value: 'Omeprazol 20 mg' } })

  fireEvent.keyDown(screen.getByLabelText('Valor final'), { key: 'Enter', ctrlKey: true })

  await waitFor(() => {
    const posts = fetchMock.mock.calls.filter(
      ([url, init]) => init?.method === 'POST' && String(url).includes('/decisions'),
    )
    expect(posts).toHaveLength(1)
    expect(JSON.parse(posts[0][1].body)).toMatchObject({
      state: 'confirmado',
      reviewer_id: 'ana',
      final_value: 'Omeprazol 20 mg',
    })
  })
})

it('Esc cierra la edición sin guardar', async () => {
  const fetchMock = stubFetch(record())
  render(<ReviewScreen recordId='rec-1' reviewer={REVIEWER} />)
  await screen.findByRole('heading', { level: 1, name: 'Omeprazol 20 mg' })

  fireEvent.click(screen.getAllByRole('button', { name: 'Revisar' })[0])
  expect(screen.getByLabelText('Decisión de revisión')).toBeInTheDocument()

  fireEvent.keyDown(screen.getByLabelText('Decisión de revisión'), { key: 'Escape' })

  await waitFor(() =>
    expect(screen.queryByLabelText('Decisión de revisión')).not.toBeInTheDocument(),
  )
  expect(fetchMock.mock.calls.filter(
      ([url, init]) => init?.method === 'POST' && String(url).includes('/decisions'),
    )).toHaveLength(0)
})

it('documenta los atajos en la propia pantalla', async () => {
  stubFetch(record())
  render(<ReviewScreen recordId='rec-1' reviewer={REVIEWER} />)
  await screen.findByRole('heading', { level: 1, name: 'Omeprazol 20 mg' })

  fireEvent.click(screen.getByRole('button', { name: /Atajos de teclado/ }))
  expect(screen.getByText('Campo siguiente')).toBeInTheDocument()
  expect(screen.getByText('Guardar la decisión del campo activo')).toBeInTheDocument()
})

it('muestra el mensaje del backend cuando la decisión se rechaza', async () => {
  routeFetch({
    decision: {
      ok: false,
      status: 409,
      body: { detail: 'La asignación no está vigente para este revisor.' },
    },
  })

  render(<ReviewScreen recordId='rec-1' reviewer={REVIEWER} />)
  await screen.findByRole('heading', { level: 1, name: 'Omeprazol 20 mg' })

  fireEvent.click(screen.getAllByRole('button', { name: 'Revisar' })[0])
  fireEvent.change(screen.getByLabelText('Decisión de revisión'), {
    target: { value: 'confirmado' },
  })
  fireEvent.change(screen.getByLabelText('Valor final'), { target: { value: 'x' } })
  fireEvent.click(screen.getByRole('button', { name: 'Guardar decisión' }))

  // El mensaje del backend se muestra literal, sin reescribirlo.
  expect(
    await screen.findByText('La asignación no está vigente para este revisor.'),
  ).toBeInTheDocument()
})

it('recupera lo escrito sin guardar tras recargar la pantalla', async () => {
  stubFetch(record())
  const first = render(<ReviewScreen recordId='rec-1' reviewer={REVIEWER} />)
  await screen.findByRole('heading', { level: 1, name: 'Omeprazol 20 mg' })

  fireEvent.click(screen.getAllByRole('button', { name: 'Revisar' })[0])
  fireEvent.change(screen.getByLabelText('Decisión de revisión'), {
    target: { value: 'corregido' },
  })
  fireEvent.change(screen.getByLabelText('Valor final'), { target: { value: '20 mg exactos' } })
  await waitFor(() => expect(screen.getByText('Cambios sin guardar.')).toBeInTheDocument())

  // Se simula la recarga: se desmonta y se vuelve a montar la pantalla.
  first.unmount()
  stubFetch(record())
  render(<ReviewScreen recordId='rec-1' reviewer={REVIEWER} />)
  await screen.findByRole('heading', { level: 1, name: 'Omeprazol 20 mg' })

  expect(await screen.findByText(/Se ha recuperado lo que había escrito/)).toBeInTheDocument()
  expect(screen.getByLabelText('Valor final')).toHaveValue('20 mg exactos')
})

it('conserva el borrador cuando el backend rechaza el guardado', async () => {
  routeFetch({
    decision: { ok: false, status: 409, body: { detail: 'La asignación no está vigente.' } },
  })

  render(<ReviewScreen recordId='rec-1' reviewer={REVIEWER} />)
  await screen.findByRole('heading', { level: 1, name: 'Omeprazol 20 mg' })

  fireEvent.click(screen.getAllByRole('button', { name: 'Revisar' })[0])
  fireEvent.change(screen.getByLabelText('Decisión de revisión'), {
    target: { value: 'confirmado' },
  })
  fireEvent.change(screen.getByLabelText('Valor final'), { target: { value: 'valor propuesto' } })
  fireEvent.click(screen.getByRole('button', { name: 'Guardar decisión' }))

  await screen.findByText('La asignación no está vigente.')
  // Un rechazo no puede perder el trabajo ni afirmar que se guardó.
  expect(screen.getByText('No se ha guardado.')).toBeInTheDocument()
  expect(screen.getByLabelText('Valor final')).toHaveValue('valor propuesto')
})

it('retira el borrador cuando la decisión queda firmada', async () => {
  const saved = record()
  saved.blocks[0].values[0] = {
    ...saved.blocks[0].values[0],
    validation_state: 'confirmado' as const,
    history: [
      {
        sequence: 1,
        state: 'confirmado' as const,
        final_value: 'Omeprazol 20 mg',
        comment: null,
        reviewer_id: 'ana',
        reviewer_assurance: 'declarada',
        decided_at: '2026-09-08T10:00:00+00:00',
      },
    ],
  }
  routeFetch({ afterDecision: saved })

  render(<ReviewScreen recordId='rec-1' reviewer={REVIEWER} />)
  await screen.findByRole('heading', { level: 1, name: 'Omeprazol 20 mg' })

  fireEvent.click(screen.getAllByRole('button', { name: 'Revisar' })[0])
  fireEvent.change(screen.getByLabelText('Decisión de revisión'), {
    target: { value: 'confirmado' },
  })
  fireEvent.change(screen.getByLabelText('Valor final'), { target: { value: 'Omeprazol 20 mg' } })
  fireEvent.click(screen.getByRole('button', { name: 'Guardar decisión' }))

  await screen.findByText('Decisión guardada.')
  // El borrador desaparece: ya no hay trabajo sin firmar que proteger.
  await waitFor(() =>
    expect(window.localStorage.getItem('farmalidacion.draft.rec-1.value-1')).toBeNull(),
  )
})

it('no precarga ningún valor bajo la política conservadora (DEV-512)', async () => {
  stubFetch(record())
  render(<ReviewScreen recordId='rec-1' reviewer={REVIEWER} />)
  await screen.findByRole('heading', { level: 1, name: 'Omeprazol 20 mg' })

  fireEvent.click(screen.getAllByRole('button', { name: 'Revisar' })[0])

  // El desplegable arranca sin decisión y el valor final vacío, aunque la
  // fuente declare un valor: proponerlo sería decidir por el revisor.
  expect(screen.getByLabelText('Decisión de revisión')).toHaveValue('')
  fireEvent.change(screen.getByLabelText('Decisión de revisión'), {
    target: { value: 'confirmado' },
  })
  expect(screen.getByLabelText('Valor final')).toHaveValue('')
})

it('muestra el aviso de criterio clínico que declara el backend', async () => {
  stubFetch(record())
  render(<ReviewScreen recordId='rec-1' reviewer={REVIEWER} />)
  await screen.findByRole('heading', { level: 1, name: 'Omeprazol 20 mg' })

  fireEvent.click(screen.getAllByRole('button', { name: 'Revisar' })[0])
  // Se muestra literal: reformularlo perdería la razón por la que está.
  expect(
    screen.getByText(/La ficha técnica no declara este dato/),
  ).toBeInTheDocument()
})
