import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { ExportsScreen } from './ExportsScreen'

const REVIEWER = {
  identifier: 'ana',
  display_name: 'Ana',
  assurance: 'configured',
  role: 'farmaceutico' as const,
  role_label: 'Farmacéutico/a',
  may_sign_pharmacist_states: true,
}

/**
 * Exportaciones archivadas (DEV-604/605).
 *
 * Lo que se comprueba es que la pantalla no pueda dar por completa una
 * exportacion que dejo fichas fuera, y que no presente un perfil como
 * aceptado por el proveedor.
 */

const RUN = {
  run_id: 'run-1',
  profile_name: 'perfil-prueba',
  profile_version: 'abc123def456',
  format: 'csv',
  status: 'completado',
  actor_id: 'ana',
  row_count: 1200,
  excluded_count: 37,
  content_hash: 'a'.repeat(64),
  byte_size: 40960,
  created_at: '2026-09-08T10:00:00+00:00',
}

const EXCLUSION = {
  target_record_id: 'rec-2',
  field_name: 'DESCRIPCION',
  severity: 'bloqueante',
  rule: 'campo_sin_validar',
  detail: 'DESCRIPCION no tiene ninguna decision registrada.',
  observed_state: 'pendiente',
}

function stub(handler: (url: string) => unknown) {
  const mock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
    void _init
    return { ok: true, status: 200, json: async () => handler(String(input)) } as Response
  })
  vi.stubGlobal('fetch', mock)
  return mock
}

afterEach(() => vi.unstubAllGlobals())

it('muestra siempre entregadas y excluidas juntas', async () => {
  stub(() => [RUN])
  render(<ExportsScreen reviewer={REVIEWER} />)

  // Un listado que solo dijera cuantas salieron haria indistinguible una
  // exportacion completa de una a la que le faltan fichas.
  // El separador de miles depende del locale del entorno; lo que importa es
  // que ambos numeros esten presentes, no como se agrupan.
  expect(await screen.findByText(/^1[.,]?200$/)).toBeInTheDocument()
  expect(screen.getByText('37')).toBeInTheDocument()
  expect(screen.getByText('Completada')).toBeInTheDocument()
})

it('no presenta ningun perfil como aceptado por el proveedor', async () => {
  stub(() => [RUN])
  render(<ExportsScreen reviewer={REVIEWER} />)
  expect(await screen.findByText(/D-011 sigue pendiente/)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Descargar' })).toHaveAttribute(
    'href',
    'http://localhost:8000/exports/run-1/artifact',
  )
})

it('explica el caso vacio en lugar de mostrar una tabla en blanco', async () => {
  stub(() => [])
  render(<ExportsScreen reviewer={REVIEWER} />)
  expect(await screen.findByText('Sin exportaciones')).toBeInTheDocument()
})

it('despliega las exclusiones con su regla y su motivo', async () => {
  stub((url) => (url.includes('/exclusions') ? [EXCLUSION] : [RUN]))
  render(<ExportsScreen reviewer={REVIEWER} />)

  fireEvent.click(await screen.findByRole('button', { name: 'Ver' }))

  expect(await screen.findByText('campo_sin_validar')).toBeInTheDocument()
  expect(screen.getByText('Bloqueante')).toBeInTheDocument()
  expect(screen.getByText(/no tiene ninguna decision registrada/)).toBeInTheDocument()
  expect(screen.getByText('rec-2')).toBeInTheDocument()
})

it('declara cuando una ejecucion quedo bloqueada por el contrato', async () => {
  stub(() => [{ ...RUN, status: 'bloqueado_por_contrato', row_count: 0 }])
  render(<ExportsScreen reviewer={REVIEWER} />)
  expect(await screen.findByText('Bloqueada por contrato')).toBeInTheDocument()
})

it('crea una exportacion firmada y refresca el historial', async () => {
  const mock = stub((url) => url.endsWith('/exports') ? [RUN] : [])
  mock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
    if (init?.method === 'POST') {
      return { ok: true, status: 201, json: async () => ({ run_id: 'run-2', status: 'completado', delivered_rows: 1, excluded_count: 0, blocking_count: 0, content_hash: 'b'.repeat(64), provider_accepted: false }) } as Response
    }
    return { ok: true, status: 200, json: async () => [RUN] } as Response
  })
  render(<ExportsScreen reviewer={REVIEWER} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Generar exportación' }))
  expect(await screen.findByRole('status')).toHaveTextContent('1 entregadas y 0 excluidas')
  const post = mock.mock.calls.find((call) => call[1]?.method === 'POST')
  expect(JSON.parse(String(post?.[1]?.body))).toMatchObject({ actor_id: 'ana', fmt: 'csv', columns: [{ name: 'DESCRIPCION', source_field: 'DESCRIPCION' }] })
})

it('bloquea la firma cuando no hay revisor', async () => {
  stub(() => [])
  render(<ExportsScreen reviewer={null} />)
  expect(await screen.findByRole('button', { name: 'Generar exportación' })).toBeDisabled()
  expect(screen.getByText(/Seleccione un revisor en la cabecera/)).toBeInTheDocument()
})
