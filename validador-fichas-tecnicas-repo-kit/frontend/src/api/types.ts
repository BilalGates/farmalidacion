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

export interface FieldMaintenanceEntry {
  sequence: number
  before_value: string | null
  after_value: string | null
  actor_id: string
  actor_assurance: string
  reason: string
  recorded_at: string
}

export interface FieldMaintenanceWrite {
  expected_sequence: number
  value: string | null
  actor_id: string
  reason: string
}

export interface QuarantinedField {
  source_column_index: number
  field_name: string
  literal_value: string | null
  maintained_value: string | null
  observed_type: string
  maintenance_sequence: number
  maintenance_history: FieldMaintenanceEntry[]
}

export interface QuarantinedSourceRow {
  id: string
  source_workbook: string
  source_locator: string
  reason_code: string
  reason: string
  fields: QuarantinedField[]
}

export interface QuarantinedSourceRowPage {
  items: QuarantinedSourceRow[]
  total: number
}

export interface FieldValue {
  id: string
  field_name: string
  source_column_index?: number | null
  literal_value: string | null
  maintained_value?: string | null
  maintenance_sequence?: number
  maintenance_history?: FieldMaintenanceEntry[]
  observed_type: string
  logical_state: string
  provenance: Provenance[]
  validation_state: ValidationState
  conflict_status: string
  has_conflict: boolean
  history: Decision[]
  /**
   * Política de pre-relleno del campo (especificación 9, DEV-512).
   *
   * La decide el backend y la pantalla la obedece: reimplementarla aquí
   * crearía un segundo sitio donde relajarla. `proposed_value` llega a `null`
   * en toda política protegida, por construcción del backend.
   */
  prefill_policy: 'proponer_valor' | 'proponer_opciones' | 'solo_evidencia' | 'oculto'
  prefill_presentation: 'valor_precargado' | 'opciones_sin_marcar' | 'casilla_vacia' | 'no_visible'
  proposed_value: string | null
  prefill_options: string[]
  prefill_warning: string | null
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

export type ReviewerRole = 'farmaceutico' | 'tecnico' | 'cientifico_datos' | 'otro'

export interface Reviewer {
  identifier: string
  display_name: string
  assurance: string
  role: ReviewerRole
  role_label: string
  /** Si puede declarar «no consta» y «no aplica». Lo calcula el backend. */
  may_sign_pharmacist_states: boolean
}

/** Revisor tal y como lo ve la pantalla de gestión, activos e inactivos. */
export interface ReviewerAdmin {
  identifier: string
  display_name: string
  role: ReviewerRole
  role_label: string
  active: boolean
}

export interface ReviewerRoleOption {
  value: ReviewerRole
  label: string
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

/* --------------------------------------------------------------------------
 * Consulta de datos reales (vertical de visibilidad).
 *
 * `origin` separa explícitamente lo importado de lo cargado como demostración.
 * No existe un valor «ambos»: mezclarlos es precisamente lo que se evita.
 * ------------------------------------------------------------------------ */

export type DataOrigin = 'real' | 'demo'

/** Modo declarado por el backend que sirve la aplicación. */
export type DataMode = 'real' | 'demo'

/**
 * Diagnóstico de qué base está sirviendo el backend.
 *
 * `mode` es lo declarado al arrancar; los recuentos son lo almacenado. La
 * interfaz muestra ambos porque pueden contradecirse: arrancar en REAL sobre
 * una base sin importar deja `consistent` en falso, y eso debe verse.
 */
export interface DatabaseInfo {
  readonly mode: DataMode
  readonly backend: string
  readonly database: string
  readonly records_total: number
  readonly records_real: number
  readonly records_demo: number
  readonly import_batches: number
  readonly consistent: boolean
}

export interface Metric {
  key: string
  label: string
  value: number
}

export interface PipelineStage {
  key: string
  label: string
  status: string
  detail: string
}

export interface Dashboard {
  metrics: Metric[]
  pipeline: PipelineStage[]
  last_import_at: string | null
  empty: boolean
}

export interface SourceSummary {
  key: string
  name: string
  source_type: string
  status: string
  versions: number
  latest_version: string | null
  latest_content_hash: string | null
  last_updated_at: string | null
  batches: number
  records: number
  diagnostics: number
  quarantined_rows: number
}

export interface SourceSheet {
  sheet_name: string
  sheet_ordinal: number
  data_row_count: number
  material_value_count: number
}

export interface SourceDetail extends SourceSummary {
  sheets: SourceSheet[]
  batch_ids: string[]
}

export interface SourceList {
  items: SourceSummary[]
  total: number
}

export interface ImportSummary {
  id: string
  source_system: string
  source_locator: string
  source_version: string | null
  content_hash: string
  importer_name: string
  importer_version: string
  status: string
  created_at: string
  completed_at: string | null
  processed_rows: number | null
  retained_records: number
  quarantined_rows: number
  diagnostics: number
  errors: number
}

export interface Incident {
  severity: string
  code: string
  message: string
  source_locator: string | null
  occurrence_count: number
}

export interface ImportDetail extends ImportSummary {
  sheets: SourceSheet[]
  incidents: Incident[]
}

export interface ImportList {
  items: ImportSummary[]
  total: number
}

export interface RealRecordRow {
  id: string
  entity_type: string
  origin: DataOrigin
  display_name: string | null
  identifier: string | null
  source_system: string | null
  block_count: number
  field_count: number
  /** Vocabulario cerrado: el listado no muestra estados que no existan. */
  review_state: ReviewState
}

export interface RealRecordPage {
  items: RealRecordRow[]
  total: number
  limit: number
  offset: number
}

export interface EmptySourceColumn {
  source_column_index: number
  field_name: string
}

export type CatalogIdentityType =
  | 'commercial_product'
  | 'authorization'
  | 'presentation'
  | 'dcpf'
  | 'dcp'
  | 'dcsa'
  | 'active_ingredient'

export type CatalogSourceWorkbook = 'especialidades' | 'medicamentos' | 'principios_activos'
export type CatalogIdentitySort = 'name_asc' | 'name_desc' | 'code_asc' | 'code_desc'

export interface CatalogIdentity {
  id: string
  identity_type: CatalogIdentityType
  code: string | null
  display_name: string
  target_record_id: string | null
  source_system: string
  source_version: string
  source_workbook?: CatalogSourceWorkbook | null
  source_literal: string | null
  active: boolean
  version: number
  commercial_class?: string | null
  conditions?: string[]
}

export interface CatalogIdentityPage {
  items: CatalogIdentity[]
  total: number
  limit: number
  offset: number
}

export interface CatalogRevision {
  sequence: number
  action: string
  before_state: string | null
  after_state: string
  actor_id: string
  actor_assurance: string
  reason: string
  recorded_at: string
}

export interface CatalogRelation {
  id: string
  relation_type: string
  direction: 'incoming' | 'outgoing'
  ordinal: number | null
  related_identity: CatalogIdentity
}

export interface CatalogClassification {
  id: string
  classification_type: 'commercial_class' | 'condition'
  value: string
  source_system: string
  source_version: string
  source_fragment_id: string | null
  active: boolean
}

export interface ValueProvenance {
  source_system: string | null
  document_name: string | null
  source_locator: string | null
  source_version: string | null
  content_hash: string | null
  locator: string
  locator_type: string
  provenance_role: string
  import_batch_id: string | null
}

export interface RealRecordValue {
  id: string
  field_name: string
  literal_value: string | null
  observed_type: string
  logical_state: string
  provenance: ValueProvenance[]
}

export interface RealRecordBlock {
  id: string
  block_type: string
  ordinal: number
  values: RealRecordValue[]
}

export interface RecordSourceAvailability {
  key: string
  label: string
  status: string
  detail: string
}

export interface RealRecordDetail {
  id: string
  entity_type: string
  origin: DataOrigin
  display_name: string | null
  identifier: string | null
  blocks: RealRecordBlock[]
  sources: RecordSourceAvailability[]
}

/** Ocurrencia de un bloque repetible (DEV-507). */
export interface BlockOccurrence {
  occurrence_id: string
  ordinal: number
  values: [string, string | null][]
  /** Procede de una fuente importada. Una creada por el revisor no. */
  from_source: boolean
  not_applicable: boolean
  comment: string | null
}

export type BlockOperation =
  | 'crear'
  | 'eliminar'
  | 'reordenar'
  | 'fusionar'
  | 'marcar_no_aplicable'
  | 'revertir_no_aplicable'

export interface BlockEditWrite {
  operation: BlockOperation
  reviewer_id: string
  occurrence_id?: string
  ordered_ids?: string[]
  source_id?: string
  target_id?: string
  values?: [string, string | null][]
  comment?: string
}

export interface BlockEditRecord {
  sequence: number
  block_type: string
  operation: BlockOperation
  affected_ids: string[]
  comment: string | null
  reviewer_id: string
  reviewer_assurance: string
  edited_at: string
}

/* Fase 6: los contratos concretos viven junto a sus funciones en `client.ts`;
   aquí se reexportan para que las pantallas importen de un solo sitio. */
export type {
  BlindField,
  ExportExclusionRow,
  ExportRunSummary,
  HistoryEntry,
  SecondReviewItem,
} from './client'
