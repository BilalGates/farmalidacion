/**
 * Tipos del contrato HTTP del backend.
 *
 * Se declaran a mano y no se generan: mantenerlos explícitos obliga a que un
 * cambio del contrato se note al compilar en lugar de manifestarse en pantalla.
 */

export type ValidationState =
  | 'pendiente'
  | 'confirmado'
  | 'corregido'
  | 'no_consta'
  | 'no_aplica'
  | 'descartado'
  | 'revision_pendiente'

/** Estado agregado de un registro en el listado. Lo calcula el backend. */
export type ReviewState = 'pendiente' | 'en_revision' | 'validado' | 'requiere_revision'

/** Rol de la fuente que afirma un valor (ADR-0007). */
export type ProvenanceRole =
  | 'master_baseline'
  | 'cima_structured'
  | 'technical_sheet'
  | 'pharmacist_decision'
  | 'authorized_transformation'
  | 'external_source'
  | string

export interface Provenance {
  source_fragment_id: string
  document_version_id: string
  locator_type: string
  locator: string
  literal_text: string | null
  provenance_role: ProvenanceRole
}

export interface Decision {
  sequence: number
  state: ValidationState
  final_value: string | null
  comment: string | null
  reviewer_id: string
  reviewer_assurance: string
  decided_at: string
}

export interface FieldValue {
  id: string
  field_name: string
  literal_value: string | null
  observed_type: string
  logical_state: string
  provenance: Provenance[]
  validation_state: ValidationState
  conflict_status: string
  has_conflict: boolean
  history: Decision[]
}

export interface BlockInstance {
  id: string
  block_type: string
  ordinal: number
  values: FieldValue[]
}

export interface ExternalIdentifier {
  source_system: string
  source_identifier: string
  source_version: string
}

export interface TargetRecord {
  id: string
  entity_type: string
  external_identifiers: ExternalIdentifier[]
  blocks: BlockInstance[]
}

export interface RecordSummary {
  id: string
  entity_type: string
  display_name: string | null
  active_ingredient: string | null
  primary_identifier: string | null
  block_count: number
  field_count: number
  pending_count: number
  resolved_count: number
  conflict_count: number
  review_state: ReviewState
  last_reviewed_at: string | null
}

export interface RecordList {
  items: RecordSummary[]
  total: number
}

export interface Reviewer {
  identifier: string
  display_name: string
  assurance: string
}

export interface DecisionWrite {
  state: ValidationState
  reviewer_id: string
  reviewer_role?: string
  final_value?: string | null
  comment?: string | null
  applicable_sources?: string[]
  required_sources?: string[]
  reviewed_sources?: string[]
  field_required?: boolean
}
