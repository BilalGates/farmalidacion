import { fireEvent, render, screen, within } from '@testing-library/react'
import { expect, it } from 'vitest'

import type { Provenance } from '../api/types'
import { ProvenanceList, parseEvidenceRow } from './ProvenanceList'

/** Fila de origen tal y como la serializa la importación de maestros. */
const FILA = JSON.stringify([
  { column: 1, formula: null, header: 'BN_IDEXTERNO', literal_value: '701897', observed_type: 'shared_string' },
  { column: 4, formula: null, header: 'DESCRIPCION', literal_value: 'ESCITALOPRAM 15 MG', observed_type: 'shared_string' },
  { column: 9, formula: null, header: 'CANTIDAD', literal_value: '176.805', observed_type: 'number' },
])

function procedencia(literalText: string | null): Provenance[] {
  return [
    {
      source_fragment_id: 'frag-1',
      provenance_role: 'master_baseline',
      document_version_id: 'version-1',
      locator_type: 'excel_row',
      locator: '{"row":8008,"sheet":"Excipientes"}',
      literal_text: literalText,
    } as Provenance,
  ]
}

it('muestra el contexto vecino y permite recuperar la fila completa sin perder vacíos ni fórmulas', () => {
  const cells = Array.from({ length: 7 }, (_, column) => ({ column, header: `CAMPO_${column}`, literal_value: column === 0 ? null : `valor ${column}`, formula: column === 6 ? 'A1' : null, observed_type: 'text' }))
  render(<ProvenanceList provenance={procedencia(JSON.stringify(cells))} highlightField='CAMPO_3' contextual />)
  expect(screen.getAllByRole('row')).toHaveLength(3)
  expect(screen.queryByRole('row', { name: /CAMPO_0/ })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: /Ver fila completa/ }))
  expect(screen.getAllByRole('row')).toHaveLength(7)
  expect(screen.getByRole('row', { name: /CAMPO_0/ })).toHaveTextContent('sin valor')
  expect(screen.getByRole('row', { name: /CAMPO_6/ })).toHaveTextContent('=A1')
  fireEvent.click(screen.getByRole('button', { name: /Ver fragmento con contexto/ }))
  expect(screen.getAllByRole('row')).toHaveLength(3)
})

it('presenta la fila de origen como campos legibles, no como JSON', () => {
  render(<ProvenanceList provenance={procedencia(FILA)} />)

  // La cabecera y su valor se leen por separado; el JSON crudo no aparece.
  expect(screen.getByRole('row', { name: /BN_IDEXTERNO/ })).toBeInTheDocument()
  expect(screen.getByText('ESCITALOPRAM 15 MG')).toBeInTheDocument()
  expect(screen.getByText('176.805')).toBeInTheDocument()
  // El JSON sigue existiendo, pero replegado en los detalles técnicos: la vista
  // principal ya no obliga a descifrarlo a ojo.
  expect(screen.getByText(FILA).closest('details')).not.toBeNull()
})

it('permite ampliar una fila de tres celdas cuando el campo activo está en un extremo', () => {
  render(<ProvenanceList provenance={procedencia(FILA)} highlightField='BN_IDEXTERNO' contextual />)
  expect(screen.getAllByRole('row')).toHaveLength(2)
  fireEvent.click(screen.getByRole('button', { name: /Ver fila completa/ }))
  expect(screen.getAllByRole('row')).toHaveLength(3)
  expect(screen.getByRole('button', { name: /Ver fragmento con contexto/ })).toBeInTheDocument()
})

it('destaca la celda del campo que se revisa', () => {
  const { container } = render(
    <ProvenanceList provenance={procedencia(FILA)} highlightField='CANTIDAD' />,
  )

  const destacadas = container.querySelectorAll('.evidence-row__cell--active')
  expect(destacadas).toHaveLength(1)
  expect(within(destacadas[0] as HTMLElement).getByText('176.805')).toBeInTheDocument()
})

it('conserva el fragmento original entre los detalles técnicos', () => {
  render(<ProvenanceList provenance={procedencia(FILA)} />)

  // Reformatear no puede perder el original: la trazabilidad exige poder
  // comprobar exactamente lo que se importó.
  expect(screen.getByText(FILA)).toBeInTheDocument()
})

it('muestra tal cual un fragmento que no sea una fila serializada', () => {
  render(<ProvenanceList provenance={procedencia('Texto literal del maestro.')} />)

  // Sin duplicarlo: si no se reformatea, el original ya está a la vista.
  expect(screen.getAllByText('Texto literal del maestro.')).toHaveLength(1)
})

it('no interpreta como fila lo que no lo es', () => {
  expect(parseEvidenceRow('texto suelto')).toBeNull()
  expect(parseEvidenceRow('[]')).toBeNull()
  expect(parseEvidenceRow('[{"otra":"forma"}]')).toBeNull()
})
