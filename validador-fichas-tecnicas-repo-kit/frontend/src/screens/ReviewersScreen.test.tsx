import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { ReviewersScreen } from './ReviewersScreen'

afterEach(() => vi.unstubAllGlobals())

const ROLES = [
  { value: 'farmaceutico', label: 'Farmacéutico' },
  { value: 'tecnico', label: 'Técnico' },
  { value: 'cientifico_datos', label: 'Científico de datos' },
]

const REVIEWERS = [
  { identifier: 'ana', display_name: 'Ana Ruiz', role: 'farmaceutico', role_label: 'Farmacéutico', active: true },
  { identifier: 'bea', display_name: 'Bea Gil', role: 'tecnico', role_label: 'Técnico', active: false },
]

function stub(onWrite?: (url: string, init?: RequestInit) => unknown) {
  const mock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
    const url = String(input)
    const ok = (body: unknown) =>
      new Response(JSON.stringify(body), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    if (init?.method) {
      onWrite?.(url, init)
      return ok(REVIEWERS[0])
    }
    if (url.includes('/reviewers/roles')) return ok(ROLES)
    return ok(REVIEWERS)
  })
  vi.stubGlobal('fetch', mock)
  return mock
}

it('lista revisores activos e inactivos con su rol', async () => {
  stub()
  render(<ReviewersScreen />)

  expect(await screen.findByText('Ana Ruiz')).toBeVisible()
  // El inactivo sigue listado: si desapareciera no habría forma de reactivarlo.
  expect(screen.getByText('Bea Gil')).toBeVisible()
  expect(screen.getByText('Activo')).toBeVisible()
  expect(screen.getByText('Inactivo')).toBeVisible()
})

it('ofrece desactivar a quien está activo y reactivar a quien no', async () => {
  const writes: string[] = []
  stub((url, init) => writes.push(`${init?.method} ${url} ${String(init?.body)}`))
  render(<ReviewersScreen />)

  await screen.findByText('Ana Ruiz')
  fireEvent.click(screen.getByRole('button', { name: 'Desactivar' }))
  await waitFor(() => expect(writes).toHaveLength(1))
  expect(writes[0]).toContain('/reviewers/ana/active')
  expect(writes[0]).toContain('"active":false')

  fireEvent.click(screen.getByRole('button', { name: 'Reactivar' }))
  await waitFor(() => expect(writes).toHaveLength(2))
  expect(writes[1]).toContain('"active":true')
})

it('da de alta un revisor con su rol', async () => {
  const writes: string[] = []
  stub((url, init) => writes.push(`${init?.method} ${url} ${String(init?.body)}`))
  render(<ReviewersScreen />)

  await screen.findByText('Ana Ruiz')
  fireEvent.change(screen.getByLabelText('Identificador'), { target: { value: 'carlos' } })
  fireEvent.change(screen.getByLabelText('Nombre'), { target: { value: 'Carlos Vera' } })
  fireEvent.change(screen.getByLabelText('Rol'), { target: { value: 'cientifico_datos' } })
  fireEvent.click(screen.getByRole('button', { name: 'Añadir revisor' }))

  await waitFor(() => expect(writes).toHaveLength(1))
  expect(writes[0]).toContain('"identifier":"carlos"')
  expect(writes[0]).toContain('"role":"cientifico_datos"')
})

it('muestra el motivo cuando el backend rechaza la operación', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input)
      if (init?.method) {
        // La regla vive en el backend; la pantalla enseña lo que responde en
        // lugar de decidir por su cuenta quién puede retirarse.
        return new Response(
          JSON.stringify({ detail: 'No se puede desactivar al último farmacéutico activo.' }),
          { status: 400, headers: { 'Content-Type': 'application/json' } },
        )
      }
      const body = url.includes('/roles') ? ROLES : REVIEWERS
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }),
  )
  render(<ReviewersScreen />)

  await screen.findByText('Ana Ruiz')
  fireEvent.click(screen.getByRole('button', { name: 'Desactivar' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('último farmacéutico')
})
