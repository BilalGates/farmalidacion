import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import type { BlockOccurrence } from '../api/types'
import { BlockEditor } from './BlockEditor'

/**
 * Pruebas del editor de bloques repetibles (DEV-507).
 *
 * Lo que importa aquí es que la interfaz no permita perder dato de origen sin
 * declararlo y que muestre literalmente el motivo cuando el backend rechaza
 * una operación, en lugar de reinterpretarlo.
 */

const REVIEWER = { identifier: 'ana', display_name: 'Ana', assurance: 'declarada' as const }

function occurrences(): BlockOccurrence[] {
  return [
    {
      occurrence_id: 'blk-1',
      ordinal: 1,
      values: [['DESCRIPCION', 'primera']],
      from_source: true,
      not_applicable: false,
      comment: null,
    },
    {
      occurrence_id: 'blk-2',
      ordinal: 2,
      values: [['DESCRIPCION', 'segunda']],
      from_source: false,
      not_applicable: false,
      comment: null,
    },
  ]
}

afterEach(() => vi.unstubAllGlobals())

function stub(response: unknown, ok = true, status = 200) {
  const mock = vi.fn().mockResolvedValue({
    ok,
    status,
    json: async () => response,
  } as Response)
  vi.stubGlobal('fetch', mock)
  return mock
}

it('distingue una ocurrencia importada de una añadida por revisión', () => {
  stub([])
  render(
    <BlockEditor
      recordId='rec-1'
      blockType='general'
      occurrences={occurrences()}
      reviewer={REVIEWER}
      onChange={() => {}}
    />,
  )
  expect(screen.getByText('Importada')).toBeInTheDocument()
  expect(screen.getByText('Añadida por revisión')).toBeInTheDocument()
})

it('no permite editar sin revisor seleccionado', () => {
  stub([])
  render(
    <BlockEditor
      recordId='rec-1'
      blockType='general'
      occurrences={occurrences()}
      reviewer={null}
      onChange={() => {}}
    />,
  )
  expect(screen.getByRole('button', { name: 'Añadir ocurrencia' })).toBeDisabled()
  expect(screen.getByText(/Seleccione un revisor/)).toBeInTheDocument()
})

it('exige motivo antes de eliminar y advierte si la ocurrencia es importada', async () => {
  const mock = stub(occurrences())
  render(
    <BlockEditor
      recordId='rec-1'
      blockType='general'
      occurrences={occurrences()}
      reviewer={REVIEWER}
      onChange={() => {}}
    />,
  )

  fireEvent.click(screen.getAllByRole('button', { name: 'Eliminar' })[0])

  // La advertencia nombra la alternativa que conserva el dato.
  expect(screen.getByText(/Marcarla «no aplica» la conserva/)).toBeInTheDocument()
  // Sin motivo no se puede confirmar: el backend lo exige y descubrirlo con un
  // 400 haría repetir el trabajo.
  expect(screen.getByRole('button', { name: 'Confirmar' })).toBeDisabled()
  expect(mock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(0)

  fireEvent.change(screen.getByLabelText('Motivo de la operación'), {
    target: { value: 'La fuente la duplicaba.' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Confirmar' }))

  await waitFor(() => {
    const posts = mock.mock.calls.filter(([, init]) => init?.method === 'POST')
    expect(posts).toHaveLength(1)
    expect(JSON.parse(posts[0][1].body)).toEqual({
      operation: 'eliminar',
      occurrence_id: 'blk-1',
      comment: 'La fuente la duplicaba.',
      reviewer_id: 'ana',
    })
  })
})

it('reordenar envía siempre la lista completa', async () => {
  const mock = stub(occurrences())
  render(
    <BlockEditor
      recordId='rec-1'
      blockType='general'
      occurrences={occurrences()}
      reviewer={REVIEWER}
      onChange={() => {}}
    />,
  )

  fireEvent.click(screen.getByRole('button', { name: 'Bajar ocurrencia 1' }))

  await waitFor(() => {
    const posts = mock.mock.calls.filter(([, init]) => init?.method === 'POST')
    expect(posts).toHaveLength(1)
    // Omitir una ocurrencia la eliminaría de hecho: se envían las dos.
    expect(JSON.parse(posts[0][1].body).ordered_ids).toEqual(['blk-2', 'blk-1'])
  })
})

it('no ofrece subir la primera ni bajar la última', () => {
  stub([])
  render(
    <BlockEditor
      recordId='rec-1'
      blockType='general'
      occurrences={occurrences()}
      reviewer={REVIEWER}
      onChange={() => {}}
    />,
  )
  expect(screen.getByRole('button', { name: 'Subir ocurrencia 1' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Bajar ocurrencia 2' })).toBeDisabled()
})

it('muestra literalmente el motivo por el que el backend rechaza una fusión', async () => {
  const mock = vi.fn()
  mock.mockResolvedValueOnce({
    ok: false,
    status: 400,
    json: async () => ({
      detail: 'Las ocurrencias declaran valores distintos para DESCRIPCION; resuelva el conflicto antes de fusionar.',
    }),
  } as Response)
  vi.stubGlobal('fetch', mock)

  render(
    <BlockEditor
      recordId='rec-1'
      blockType='general'
      occurrences={occurrences()}
      reviewer={REVIEWER}
      onChange={() => {}}
    />,
  )

  fireEvent.click(screen.getAllByRole('button', { name: 'Fusionar' })[0])
  fireEvent.change(screen.getByLabelText('Ocurrencia de destino'), {
    target: { value: 'blk-2' },
  })
  fireEvent.change(screen.getByLabelText('Motivo de la operación'), {
    target: { value: 'Duplicadas.' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Confirmar' }))

  expect(await screen.findByText(/valores distintos para DESCRIPCION/)).toBeInTheDocument()
})

it('ofrece revertir sobre una ocurrencia ya marcada', () => {
  stub([])
  const marked = occurrences()
  marked[0] = { ...marked[0], not_applicable: true, comment: 'Fuera de alcance.' }
  render(
    <BlockEditor
      recordId='rec-1'
      blockType='general'
      occurrences={marked}
      reviewer={REVIEWER}
      onChange={() => {}}
    />,
  )
  expect(screen.getByRole('button', { name: 'Revertir no aplica' })).toBeInTheDocument()
  expect(screen.getByText('No aplica')).toBeInTheDocument()
  expect(screen.getByText('Fuera de alcance.')).toBeInTheDocument()
})

it('añadir una ocurrencia no declara procedencia', async () => {
  const mock = stub(occurrences())
  render(
    <BlockEditor
      recordId='rec-1'
      blockType='general'
      occurrences={occurrences()}
      reviewer={REVIEWER}
      onChange={() => {}}
    />,
  )

  fireEvent.click(screen.getByRole('button', { name: 'Añadir ocurrencia' }))

  await waitFor(() => {
    const posts = mock.mock.calls.filter(([, init]) => init?.method === 'POST')
    expect(posts).toHaveLength(1)
    const body = JSON.parse(posts[0][1].body)
    expect(body.operation).toBe('crear')
    // Nada en la petición afirma un origen: lo decide el servidor y es ninguno.
    expect(body).not.toHaveProperty('origin_provenance')
    expect(body).not.toHaveProperty('source_fragment_id')
  })
})
