import { appConfig } from '../config'
import type {
  BlockEditRecord,
  BlockEditWrite,
  BlockOccurrence,
  CatalogIdentity,
  CatalogIdentityPage,
  CatalogIdentityType,
  CatalogRevision,
  CatalogRelation,
  CatalogClassification,
  Dashboard,
  DatabaseInfo,
  DataOrigin,
  DecisionWrite,
  ImportDetail,
  ImportList,
  RealRecordDetail,
  RealRecordPage,
  ReviewState,
  ReviewerAdmin,
  ReviewerRole,
  ReviewerRoleOption,
  RecordList,
  Reviewer,
  SourceDetail,
  SourceList,
  TargetRecord,
} from './types'

/**
 * Error de aplicación devuelto por el backend.
 *
 * El mensaje llega en español desde el backend y se muestra tal cual. No se
 * reescribe: los mensajes de las barreras clínicas explican *por qué* una
 * decisión no es admisible, y reformularlos perdería esa explicación.
 */
export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 30_000)
  let response: Response
  try {
    response = await fetch(`${appConfig.apiBaseUrl}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      signal: controller.signal,
      ...init,
    })
  } catch {
    if (controller.signal.aborted) {
      throw new ApiError('La solicitud ha tardado demasiado. Inténtelo de nuevo.', 0)
    }
    throw new ApiError('No se ha podido contactar con el servidor.', 0)
  } finally {
    clearTimeout(timeout)
  }
  if (!response.ok) {
    let detail = 'Se ha producido un error inesperado.'
    try {
      const body = (await response.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      // Un cuerpo ilegible no debe ocultar el código de estado.
    }
    throw new ApiError(detail, response.status)
  }
  // 204 no trae cuerpo: pedir el JSON lanzaría y convertiría un éxito en error.
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export function fetchRecords(params: { q?: string; estado?: string } = {}): Promise<RecordList> {
  const search = new URLSearchParams()
  if (params.q) search.set('q', params.q)
  if (params.estado) search.set('estado', params.estado)
  const query = search.toString()
  return request<RecordList>(`/records${query ? `?${query}` : ''}`)
}

export function fetchRecord(id: string): Promise<TargetRecord> {
  return request<TargetRecord>(`/records/${encodeURIComponent(id)}`)
}

export interface QueueItem {
  target_record_id: string
  state: string
  version: number
  assignee_id: string | null
  priority: number
  review_set: 'oro' | 'medida' | 'corpus'
  requires_second_review: boolean
}

export interface QueueFilters {
  state?: string
  entity_type?: string
  block_type?: string
  review_set?: string
  requires_second_review?: boolean
}

export function fetchQueue(filters: QueueFilters = {}): Promise<QueueItem[]> {
  const search = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== '') search.set(key, String(value))
  })
  const query = search.toString()
  return request<QueueItem[]>(`/queue${query ? `?${query}` : ''}`)
}

export function assignQueue(id: string, reviewerId: string): Promise<QueueItem> {
  return request<QueueItem>(`/queue/${encodeURIComponent(id)}/assign`, {
    method: 'POST', body: JSON.stringify({ reviewer_id: reviewerId }),
  })
}

export function enqueueRecord(
  id: string,
  reviewSet: QueueItem['review_set'] = 'corpus',
  requiresSecondReview = false,
): Promise<QueueItem> {
  return request<QueueItem>('/queue', {
    method: 'POST',
    body: JSON.stringify({
      target_record_id: id,
      review_set: reviewSet,
      requires_second_review: requiresSecondReview,
    }),
  })
}

export function assignQueueBatch(items: QueueItem[], reviewerId: string): Promise<QueueItem[]> {
  return request<QueueItem[]>('/queue/assign-batch', {
    method: 'POST',
    body: JSON.stringify({
      reviewer_id: reviewerId,
      items: items.map((item) => ({
        target_record_id: item.target_record_id,
        expected_version: item.version,
      })),
    }),
  })
}

export function transitionQueue(item: QueueItem, reviewerId: string, state: 'en_revision' | 'pendiente'): Promise<QueueItem> {
  return request<QueueItem>(`/queue/${encodeURIComponent(item.target_record_id)}/transition`, {
    method: 'POST',
    body: JSON.stringify({ reviewer_id: reviewerId, state, expected_version: item.version }),
  })
}

export function fetchReviewers(): Promise<Reviewer[]> {
  return request<Reviewer[]>('/records/reviewers')
}

export function saveDecision(fieldValueId: string, payload: DecisionWrite): Promise<unknown> {
  return request(`/records/values/${encodeURIComponent(fieldValueId)}/decisions`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

/* --------------------------------------------------------------------------
 * Consulta de datos reales.
 * ------------------------------------------------------------------------ */

export function fetchDatabaseInfo(): Promise<DatabaseInfo> {
  return request<DatabaseInfo>('/database-info')
}

export function fetchDashboard(): Promise<Dashboard> {
  return request<Dashboard>('/insights/dashboard')
}

export function fetchSources(): Promise<SourceList> {
  return request<SourceList>('/insights/sources')
}

export function fetchSource(id: string): Promise<SourceDetail> {
  return request<SourceDetail>(`/insights/sources/${encodeURIComponent(id)}`)
}

export function fetchImports(): Promise<ImportList> {
  return request<ImportList>('/insights/imports')
}

export function fetchImport(id: string): Promise<ImportDetail> {
  return request<ImportDetail>(`/insights/imports/${encodeURIComponent(id)}`)
}

export function fetchRealRecords(params: {
  origin: DataOrigin
  q?: string
  entityType?: string
  estado?: ReviewState
  limit?: number
  offset?: number
}): Promise<RealRecordPage> {
  const search = new URLSearchParams({ origin: params.origin })
  if (params.q) search.set('q', params.q)
  if (params.entityType) search.set('entity_type', params.entityType)
  if (params.estado) search.set('estado', params.estado)
  if (params.limit !== undefined) search.set('limit', String(params.limit))
  if (params.offset !== undefined) search.set('offset', String(params.offset))
  return request<RealRecordPage>(`/insights/records?${search.toString()}`)
}

/** Revisores de la pantalla de gestión: activos e inactivos. */
export function fetchReviewerAdmin(): Promise<ReviewerAdmin[]> {
  return request<ReviewerAdmin[]>('/reviewers')
}

/** Roles disponibles. Se piden en lugar de llevarlos escritos en la pantalla. */
export function fetchReviewerRoles(): Promise<ReviewerRoleOption[]> {
  return request<ReviewerRoleOption[]>('/reviewers/roles')
}

export function createReviewer(payload: {
  identifier: string
  display_name: string
  role: ReviewerRole
}): Promise<ReviewerAdmin> {
  return request<ReviewerAdmin>('/reviewers', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function setReviewerRole(identifier: string, role: ReviewerRole): Promise<ReviewerAdmin> {
  return request<ReviewerAdmin>(`/reviewers/${encodeURIComponent(identifier)}/role`, {
    method: 'PUT',
    body: JSON.stringify({ role }),
  })
}

export function setReviewerActive(identifier: string, active: boolean): Promise<ReviewerAdmin> {
  return request<ReviewerAdmin>(`/reviewers/${encodeURIComponent(identifier)}/active`, {
    method: 'PUT',
    body: JSON.stringify({ active }),
  })
}

export function fetchRealRecord(id: string): Promise<RealRecordDetail> {
  return request<RealRecordDetail>(`/insights/records/${encodeURIComponent(id)}`)
}

export function fetchCatalogIdentities(params: {
  q?: string
  identityType?: CatalogIdentityType
  commercialClass?: string
  condition?: string
  active?: boolean
  limit?: number
  offset?: number
} = {}): Promise<CatalogIdentityPage> {
  const search = new URLSearchParams()
  if (params.q) search.set('q', params.q)
  if (params.identityType) search.set('identity_type', params.identityType)
  if (params.commercialClass) search.set('commercial_class', params.commercialClass)
  if (params.condition) search.set('condition', params.condition)
  if (params.active !== undefined) search.set('active', String(params.active))
  if (params.limit !== undefined) search.set('limit', String(params.limit))
  if (params.offset !== undefined) search.set('offset', String(params.offset))
  const query = search.toString()
  return request<CatalogIdentityPage>(`/catalog/identities${query ? `?${query}` : ''}`)
}

export function fetchCatalogIdentity(id: string): Promise<CatalogIdentity> {
  return request<CatalogIdentity>(`/catalog/identities/${encodeURIComponent(id)}`)
}

export function fetchCatalogHistory(id: string): Promise<CatalogRevision[]> {
  return request<CatalogRevision[]>(`/catalog/identities/${encodeURIComponent(id)}/history`)
}

export function fetchCatalogRelations(id: string): Promise<CatalogRelation[]> {
  return request<CatalogRelation[]>(`/catalog/identities/${encodeURIComponent(id)}/relations`)
}

export function fetchCatalogClassifications(id: string): Promise<CatalogClassification[]> {
  return request<CatalogClassification[]>(
    `/catalog/identities/${encodeURIComponent(id)}/classifications`,
  )
}

export function setCatalogClassification(
  identityId: string,
  payload: {
    classification_type: CatalogClassification['classification_type']
    value: string
    active: boolean
    actor_id: string
    reason: string
  },
): Promise<CatalogClassification> {
  const key = encodeURIComponent(`${payload.classification_type}:${payload.value}`)
  return request<CatalogClassification>(
    `/catalog/identities/${encodeURIComponent(identityId)}/classifications/${key}`,
    { method: 'PUT', body: JSON.stringify(payload) },
  )
}

export function updateCatalogIdentity(
  id: string,
  payload: {
    expected_version: number
    display_name: string
    code: string | null
    active: boolean
    actor_id: string
    reason: string
  },
): Promise<CatalogIdentity> {
  return request<CatalogIdentity>(`/catalog/identities/${encodeURIComponent(id)}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

/* --------------------------------------------------------------------------
 * Edición de bloques repetibles (DEV-507).
 * ------------------------------------------------------------------------ */

export function fetchBlockOccurrences(
  recordId: string,
  blockType: string,
): Promise<BlockOccurrence[]> {
  return request<BlockOccurrence[]>(
    `/records/${encodeURIComponent(recordId)}/blocks/${encodeURIComponent(blockType)}`,
  )
}

export function editBlock(
  recordId: string,
  blockType: string,
  payload: BlockEditWrite,
): Promise<BlockOccurrence[]> {
  return request<BlockOccurrence[]>(
    `/records/${encodeURIComponent(recordId)}/blocks/${encodeURIComponent(blockType)}`,
    { method: 'POST', body: JSON.stringify(payload) },
  )
}

export function fetchBlockHistory(recordId: string): Promise<BlockEditRecord[]> {
  return request<BlockEditRecord[]>(
    `/records/${encodeURIComponent(recordId)}/block-history`,
  )
}

/* --------------------------------------------------------------------------
 * Medición de tiempos (DEV-508/509).
 * ------------------------------------------------------------------------ */

export interface TimingSession {
  id: string
  target_record_id: string
  reviewer_id: string
  started_at: string
  ended_at: string | null
  is_synthetic: boolean
}

export function openTimingSession(
  recordId: string,
  reviewerId: string,
): Promise<TimingSession> {
  return request<TimingSession>('/timing/sessions', {
    method: 'POST',
    body: JSON.stringify({ target_record_id: recordId, reviewer_id: reviewerId }),
  })
}

/**
 * Declara un tramo de foco ya cerrado.
 *
 * No devuelve nada útil y su fallo no puede interrumpir la revisión: perder una
 * medición es tolerable, impedir que alguien valide un medicamento no lo es.
 */
export async function reportFocusSpan(
  sessionId: string,
  span: { fieldName: string; startedAt: number; endedAt: number },
): Promise<void> {
  try {
    await request<void>(`/timing/sessions/${encodeURIComponent(sessionId)}/focus`, {
      method: 'POST',
      body: JSON.stringify({
        field_name: span.fieldName,
        started_at: span.startedAt,
        ended_at: span.endedAt,
      }),
    })
  } catch {
    // Ver arriba: la medición es secundaria respecto al trabajo de revisión.
    // El tramo se pierde y la revisión continúa.
  }
}

/* --------------------------------------------------------------------------
 * Fase 6: segunda validación, exportación y auditoría.
 * ------------------------------------------------------------------------ */

export interface SecondReviewItem {
  id: string
  field_value_id: string
  target_record_id: string
  state: string
  version: number
  second_reviewer_id: string | null
}

/**
 * Vista ciega de un campo en segunda revisión.
 *
 * No contiene la decisión del primer revisor porque el backend no la sirve:
 * la ceguera vive en el dato, no en esta pantalla. Si algún día apareciese
 * aquí, sería un fallo del backend y no de la presentación.
 */
export interface BlindField {
  assignment_id: string
  field_value_id: string
  field_name: string
  literal_value: string | null
  observed_type: string
  logical_state: string
  state: string
  instruction: string
  version: number
}

export function fetchSecondReviews(reviewerId: string): Promise<SecondReviewItem[]> {
  return request<SecondReviewItem[]>(
    `/second-reviews?reviewer_id=${encodeURIComponent(reviewerId)}`,
  )
}

export function fetchBlindField(
  assignmentId: string,
  reviewerId: string,
): Promise<BlindField> {
  return request<BlindField>(
    `/second-reviews/${encodeURIComponent(assignmentId)}/blind?reviewer_id=${encodeURIComponent(reviewerId)}`,
  )
}

export function mutateSecondReview(
  assignmentId: string,
  operation: 'claim' | 'decisions' | 'reconcile',
  payload: Record<string, unknown>,
): Promise<SecondReviewItem> {
  return request<SecondReviewItem>(
    `/second-reviews/${encodeURIComponent(assignmentId)}/${operation}`,
    { method: 'POST', body: JSON.stringify(payload) },
  )
}

export interface ExportRunSummary {
  run_id: string
  profile_name: string
  profile_version: string
  format: string
  status: string
  actor_id: string
  row_count: number
  excluded_count: number
  content_hash: string | null
  byte_size: number | null
  created_at: string
}

export interface ExportExclusionRow {
  target_record_id: string
  field_name: string | null
  severity: string
  rule: string
  detail: string
  observed_state: string | null
}

export interface ExportColumnWrite {
  name: string
  source_field: string
  required?: boolean
  max_length?: number
}

export interface ExportWrite {
  actor_id: string
  profile_name: string
  fmt: 'csv' | 'txt' | 'xlsx'
  columns: ExportColumnWrite[]
  record_ids?: string[]
}

export interface ExportOutcome {
  run_id: string
  status: string
  delivered_rows: number
  excluded_count: number
  blocking_count: number
  content_hash: string | null
  provider_accepted: boolean
}

export function createExport(payload: ExportWrite): Promise<ExportOutcome> {
  return request<ExportOutcome>('/exports', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function fetchExports(): Promise<ExportRunSummary[]> {
  return request<ExportRunSummary[]>('/exports')
}

export function fetchExportExclusions(runId: string): Promise<ExportExclusionRow[]> {
  return request<ExportExclusionRow[]>(
    `/exports/${encodeURIComponent(runId)}/exclusions`,
  )
}

export function exportArtifactUrl(runId: string): string {
  return `${appConfig.apiBaseUrl}/exports/${encodeURIComponent(runId)}/artifact`
}

export interface HistoryEntry {
  occurred_at: string
  source: string
  action: string
  actor_id: string
  entity_id: string
  detail: string | null
  sequence: number | null
}

export function fetchRecordHistory(recordId: string): Promise<HistoryEntry[]> {
  return request<HistoryEntry[]>(`/audit/records/${encodeURIComponent(recordId)}`)
}

export interface MaintenanceChangeSummary {
  id: string
  nregistro: string
  occurred_at_epoch: number
  change_type: number
  areas: string[]
  old_version_id: string | null
  new_version_id: string | null
  affected_field_count: number
  has_diff: boolean
  recorded_at: string
}

export interface MaintenanceArtifactChange {
  role: string
  ordinal: number
  change_type: string
  old_locator: string | null
  new_locator: string | null
  diff_kind: string
  text_diff: string | null
}

export interface MaintenanceChangeDetail extends MaintenanceChangeSummary {
  source_sha256: string
  fetched_at: string
  diff: { changes: MaintenanceArtifactChange[] } | null
}

export function fetchMaintenanceChanges(): Promise<MaintenanceChangeSummary[]> {
  return request<MaintenanceChangeSummary[]>('/maintenance/changes')
}

export function fetchMaintenanceChange(id: string): Promise<MaintenanceChangeDetail> {
  return request<MaintenanceChangeDetail>(`/maintenance/changes/${encodeURIComponent(id)}`)
}

export interface MaintenanceRunSummary {
  id: string
  requested_date: string
  attempt: number
  status: string
  event_count: number
  error_detail: string | null
  started_at: string
  finished_at: string | null
}

export function fetchMaintenanceRuns(): Promise<MaintenanceRunSummary[]> {
  return request<MaintenanceRunSummary[]>('/maintenance/runs')
}

export interface ChatCitation {
  document_version_id: string
  section: string
  literal_text: string
}

export interface ContextualChatResult {
  status: 'answered' | 'not_found' | 'not_available'
  message: string
  citations: ChatCitation[]
}

export function askDocument(recordId: string, question: string): Promise<ContextualChatResult> {
  return request<ContextualChatResult>(`/records/${encodeURIComponent(recordId)}/chat`, {
    method: 'POST',
    body: JSON.stringify({ question }),
  })
}
