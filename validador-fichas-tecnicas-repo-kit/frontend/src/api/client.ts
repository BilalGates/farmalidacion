import { appConfig } from '../config'
import type {
  Dashboard,
  DatabaseInfo,
  DataOrigin,
  DecisionWrite,
  ImportDetail,
  ImportList,
  RealRecordDetail,
  RealRecordPage,
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
}

export function fetchQueue(): Promise<QueueItem[]> {
  return request<QueueItem[]>('/queue')
}

export function assignQueue(id: string, reviewerId: string): Promise<QueueItem> {
  return request<QueueItem>(`/queue/${encodeURIComponent(id)}/assign`, {
    method: 'POST', body: JSON.stringify({ reviewer_id: reviewerId }),
  })
}

export function enqueueRecord(id: string): Promise<QueueItem> {
  return request<QueueItem>('/queue', {
    method: 'POST', body: JSON.stringify({ target_record_id: id }),
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
  limit?: number
  offset?: number
}): Promise<RealRecordPage> {
  const search = new URLSearchParams({ origin: params.origin })
  if (params.q) search.set('q', params.q)
  if (params.limit !== undefined) search.set('limit', String(params.limit))
  if (params.offset !== undefined) search.set('offset', String(params.offset))
  return request<RealRecordPage>(`/insights/records?${search.toString()}`)
}

export function fetchRealRecord(id: string): Promise<RealRecordDetail> {
  return request<RealRecordDetail>(`/insights/records/${encodeURIComponent(id)}`)
}
