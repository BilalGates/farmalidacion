import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import type { TargetRecord } from '../api/types'
import { ReviewScreen } from './ReviewScreen'

/**
 * Pruebas de la pantalla canónica de revisión (DEV-503 / DEV-504).
 *
 * Lo que se comprueba aquí no es que la pantalla dibuje: es que la navegación
 * por teclado mueva el foco sin decidir nada, que ningún atajo firme una
 * decisión incompleta y que la evidencia mostrada sea la del campo activo.
 */

const REVIEWER = { identifier: 'ana', display_name: 'Ana', assurance: 'declarada' as const }

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

afterEach(() => {
  vi.unstubAllGlobals()
  window.localStorage.clear()
})

it('presenta las tres zonas con la evidencia del campo activo', async () => {
  stubFetch(record())
  render(<ReviewScreen recordId='rec-1' reviewer={REVIEWER} />)

  await screen.findByRole('heading', { level: 1, name: 'Omeprazol 20 mg' })
  expect(screen.getByLabelText('Campos del registro')).toBeInTheDocument()

  const evidence = screen.getByRole('complementary', { name: 'Evidencia del campo activo' })
  expect(within(evidence).getByText('Texto literal del maestro.')).toBeInTheDocument()
  expect(screen.getByText('0 de 2 campos revisados')).toBeInTheDocument()
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
  expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(0)
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
  expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(0)
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
    const posts = fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')
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
  expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(0)
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
  const mock = vi.fn()
  mock.mockResolvedValueOnce({ ok: true, status: 200, json: async () => record() } as Response)
  mock.mockResolvedValueOnce({
    ok: false,
    status: 409,
    json: async () => ({ detail: 'La asignación no está vigente para este revisor.' }),
  } as Response)
  vi.stubGlobal('fetch', mock)

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
  const mock = vi.fn()
  mock.mockResolvedValueOnce({ ok: true, status: 200, json: async () => record() } as Response)
  mock.mockResolvedValueOnce({
    ok: false,
    status: 409,
    json: async () => ({ detail: 'La asignación no está vigente.' }),
  } as Response)
  vi.stubGlobal('fetch', mock)

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
  const mock = vi.fn()
  mock.mockResolvedValueOnce({ ok: true, status: 200, json: async () => record() } as Response)
  mock.mockResolvedValueOnce({ ok: true, status: 201, json: async () => ({}) } as Response)
  mock.mockResolvedValue({ ok: true, status: 200, json: async () => saved } as Response)
  vi.stubGlobal('fetch', mock)

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
