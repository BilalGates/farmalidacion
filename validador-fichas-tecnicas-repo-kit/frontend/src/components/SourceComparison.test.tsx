import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'

import type { FieldValue, Provenance, ProvenanceRole } from '../api/types'
import { SourceComparison, divergentClaims } from './SourceComparison'

const source = (role: ProvenanceRole, literal: string | null): Provenance => ({
  source_fragment_id: `${role}-${literal}`, document_version_id: 'v1', locator_type: 'celda', locator: 'A1', literal_text: literal, provenance_role: role,
})

const value = (id: string, literal: string | null, provenance: Provenance[], conflict = false): FieldValue => ({
  id, field_name: 'FORMAFARMA', literal_value: literal, observed_type: 'CHAR(100)', logical_state: 'presente', provenance,
  validation_state: 'pendiente', conflict_status: conflict ? 'unresolved_pending_priority' : 'none', has_conflict: conflict, history: [],
  prefill_policy: 'solo_evidencia', prefill_presentation: 'casilla_vacia', proposed_value: null, prefill_options: [], prefill_warning: null,
})

it('compara valores rivales del mismo campo y resalta sólo lo que difiere', () => {
  const master = value('a', 'Cápsula dura', [source('master_baseline', 'fila 14')], true)
  const cima = value('b', 'Cápsula dura gastrorresistente', [source('cima_structured', 'sección 3')], true)
  render(<SourceComparison claims={divergentClaims(master, [master, cima])} />)
  const comparison = screen.getByLabelText('Lo que dice cada fuente')
  expect(comparison).toHaveTextContent('Cápsula dura gastrorresistente')
  expect(comparison.querySelectorAll('mark')).toHaveLength(1)
  expect(comparison.querySelector('mark')).toHaveTextContent('gastrorresistente')
})

it('no compara fragmentos de evidencia de un campo sin discrepancia', () => {
  expect(divergentClaims(value('a', 'A02BC01', [source('master_baseline', 'Fila de maestro'), source('cima_structured', 'Metadato CIMA')]))).toBeNull()
})

it('no aparece cuando las fuentes coinciden o sólo hay una', () => {
  const a = value('a', 'Omeprazol', [source('master_baseline', 'f')], true)
  const b = value('b', 'omeprazol', [source('cima_structured', 'f')], true)
  expect(divergentClaims(a, [a, b])).toBeNull()
  expect(divergentClaims(a, [a])).toBeNull()
  const { container } = render(<SourceComparison claims={null} />)
  expect(container).toBeEmptyDOMElement()
})
