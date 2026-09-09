import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { SecondReviewScreen } from './SecondReviewScreen'

/**
 * Segunda validación en la interfaz (DEV-607/608).
 *
 * La prueba importante no es que la pantalla dibuje: es que lo que llega del
 * backend por la ruta ciega no contiene la primera lectura, y que la pantalla
 * no invente una forma de pedirla.
 */

const REVIEWER = {
  identifier: 'luis',
  display_name: 'Luis',
  assurance: 'declarada' as const,
  role: 'farmaceutico' as const,
  role_label: 'Farmacéutico',
  may_sign_pharmacist_states: true,
}

const PENDING = {
  id: 'asg-1',
  field_value_id: 'fv-1',
  target_record_id: 'rec-1',
  state: 'pendiente',
  version: 1,
  second_reviewer_id: null,
}

const BLIND = {
  assignment_id: 'asg-1',
  field_value_id: 'fv-1',
  field_name: 'DESCRIPCION',
  literal_value: 'valor de origen',
  observed_type: 'texto',
  logical_state: 'valued',
  state: 'pendiente',
  instruction: 'Emita su lectura del valor de origen.',
  version: 1,
}

function stub(handler: (url: string, init?: RequestInit) => unknown) {
  const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const body = handler(String(input), init)
    return { ok: true, status: 200, json: async () => body } as Response
  })
  vi.stubGlobal('fetch', mock)
  return mock
}

afterEach(() => vi.unstubAllGlobals())

it('exige revisor para poder firmar una segunda lectura', () => {
  stub(() => [])
  render(<SecondReviewScreen reviewer={null} />)
  expect(screen.getByText(/exige saber quién la firma/)).toBeInTheDocument()
})

it('separa pendientes, discrepancias y cerradas', async () => {
  stub(() => [
    PENDING,
    { ...PENDING, id: 'asg-2', state: 'desacuerdo' },
    { ...PENDING, id: 'asg-3', state: 'acuerdo' },
  ])
  render(<SecondReviewScreen reviewer={REVIEWER} />)

  expect(await screen.findByText(/Pendientes de segunda lectura \(1\)/)).toBeInTheDocument()
  expect(screen.getByText(/Discrepancias por conciliar \(1\)/)).toBeInTheDocument()
  expect(screen.getByText(/Cerradas \(1\)/)).toBeInTheDocument()
})

it('la lectura ciega no muestra la decisión del primer revisor', async () => {
  stub((url) => (url.includes('/blind') ? BLIND : [PENDING]))
  render(<SecondReviewScreen reviewer={REVIEWER} />)

  fireEvent.click(await screen.findByRole('button', { name: 'Revisar a ciegas' }))
  await screen.findByText('Emita su lectura del valor de origen.')

  // El valor de origen sí se muestra: es lo que hay que leer.
  expect(screen.getByText('valor de origen')).toBeInTheDocument()
  // Y nada de la primera lectura, porque el backend no la sirve.
  expect(screen.queryByText(/ana/i)).not.toBeInTheDocument()
  expect(screen.queryByText(/primera decisión/i)).not.toBeInTheDocument()
  // La decisión arranca vacía: proponer una sesgaría la segunda lectura.
  expect(screen.getByLabelText('Decisión de segunda lectura')).toHaveValue('')
})

it('no registra una lectura sin decisión elegida', async () => {
  const mock = stub((url) => (url.includes('/blind') ? BLIND : [PENDING]))
  render(<SecondReviewScreen reviewer={REVIEWER} />)

  fireEvent.click(await screen.findByRole('button', { name: 'Revisar a ciegas' }))
  await screen.findByLabelText('Decisión de segunda lectura')

  expect(screen.getByRole('button', { name: 'Registrar lectura' })).toBeDisabled()
  expect(mock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(0)
})

it('envía la versión observada al registrar la lectura', async () => {
  const mock = stub((url) =>
    url.includes('/blind') ? BLIND : url.includes('/decisions') ? PENDING : [PENDING],
  )
  render(<SecondReviewScreen reviewer={REVIEWER} />)

  fireEvent.click(await screen.findByRole('button', { name: 'Revisar a ciegas' }))
  fireEvent.change(await screen.findByLabelText('Decisión de segunda lectura'), {
    target: { value: 'confirmado' },
  })
  fireEvent.change(screen.getByLabelText('Valor final de segunda lectura'), {
    target: { value: 'mi lectura' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Registrar lectura' }))

  await waitFor(() => {
    const posts = mock.mock.calls.filter(([, init]) => init?.method === 'POST')
    expect(posts).toHaveLength(1)
    const body = JSON.parse(String(posts[0][1]?.body))
    expect(body).toMatchObject({
      reviewer_id: 'luis',
      expected_version: 1,
      state: 'confirmado',
      final_value: 'mi lectura',
    })
  })
})

it('muestra literalmente la barrera que devuelve el backend', async () => {
  const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (init?.method === 'POST') {
      return {
        ok: false,
        status: 400,
        json: async () => ({
          detail: 'La doble validación exige dos revisores distintos.',
        }),
      } as Response
    }
    return {
      ok: true,
      status: 200,
      json: async () => (url.includes('/blind') ? BLIND : [PENDING]),
    } as Response
  })
  vi.stubGlobal('fetch', mock)

  render(<SecondReviewScreen reviewer={REVIEWER} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Revisar a ciegas' }))
  fireEvent.change(await screen.findByLabelText('Decisión de segunda lectura'), {
    target: { value: 'confirmado' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Registrar lectura' }))

  expect(
    await screen.findByText('La doble validación exige dos revisores distintos.'),
  ).toBeInTheDocument()
})

it('declara que conciliar no sobrescribe ninguna lectura', async () => {
  stub(() => [{ ...PENDING, state: 'desacuerdo' }])
  render(<SecondReviewScreen reviewer={REVIEWER} />)

  expect(
    await screen.findByText(/no sobrescribe ninguna de las dos lecturas/),
  ).toBeInTheDocument()
})
