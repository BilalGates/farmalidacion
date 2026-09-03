import type { ProvenanceRole, ReviewState, ValidationState } from '../api/types'

/**
 * Vocabulario visible de la interfaz, en un único lugar.
 *
 * Los estados internos son los de ADR-0004 y no se renombran: la etiqueta es
 * una traducción para la pantalla, no un estado nuevo. Mantenerlas juntas evita
 * que dos pantallas llamen de forma distinta a la misma decisión.
 */

export const VALIDATION_STATE_LABELS: Record<ValidationState, string> = {
  pendiente: 'Pendiente',
  confirmado: 'Validado',
  corregido: 'Corregido',
  no_consta: 'No consta',
  no_aplica: 'No aplica',
  descartado: 'Descartado',
  revision_pendiente: 'Requiere revisión',
}

export const REVIEW_STATE_LABELS: Record<ReviewState, string> = {
  pendiente: 'Pendiente',
  en_revision: 'En revisión',
  validado: 'Validado',
  requiere_revision: 'Requiere revisión',
}

/** Nombre visible de cada fuente. `desconocida` nunca se adivina. */
export const SOURCE_LABELS: Record<string, string> = {
  master_baseline: 'Maestro',
  cima_structured: 'CIMA',
  technical_sheet: 'Ficha técnica',
  pharmacist_decision: 'Decisión farmacéutica',
  authorized_transformation: 'Transformación autorizada',
  external_source: 'Fuente externa',
}

export function sourceLabel(role: ProvenanceRole): string {
  return SOURCE_LABELS[role] ?? role
}

/**
 * Estados de conflicto de ADR-0007 traducidos para la pantalla.
 *
 * Ninguna etiqueta afirma que una discrepancia se haya resuelto: mientras la
 * matriz de prioridad por campo no esté cargada, el motor devuelve
 * `unresolved_pending_priority` y la decisión sigue siendo humana.
 */
export const CONFLICT_LABELS: Record<string, string> = {
  no_assertions: 'Sin fuentes declaradas',
  consistent_pending_priority: 'Fuentes coincidentes',
  unresolved_pending_priority: 'Discrepancia detectada',
  human_action_required: 'Requiere decisión humana',
  unresolved_no_applicable_source: 'Sin fuente aplicable',
  unresolved_authoritative_ambiguity: 'Ambigüedad entre fuentes',
  resolved_by_accepted_priority: 'Resuelta por prioridad aprobada',
}

export function conflictLabel(status: string): string {
  return CONFLICT_LABELS[status] ?? status
}

/** Estados que un revisor puede asignar desde esta vertical. */
export const ASSIGNABLE_STATES: readonly ValidationState[] = [
  'confirmado',
  'corregido',
  'no_consta',
  'no_aplica',
  'revision_pendiente',
]

export interface RoadmapNote {
  /** Qué hace hoy esta sección. */
  readonly now: string
  /** Qué falta por implementar. */
  readonly missing: string
  /** Cómo funcionará cuando esté terminada. */
  readonly future: string
  /** Decisión o issue del que depende, para no cerrarlo por representarlo. */
  readonly dependency: string
}

/**
 * Notas de funcionalidad pendiente.
 *
 * Existen para que la demo explique el producto sin aparentar que estas
 * capacidades ya funcionan. Cada nota nombra la dependencia real del registro
 * de decisiones o del backlog: representarla en pantalla no la cierra.
 */
export const ROADMAP_NOTES: Record<string, RoadmapNote> = {
  cima: {
    now: 'Las fuentes que ve en pantalla proceden del conjunto de demostración cargado localmente.',
    missing: 'La consulta en vivo a CIMA y su versionado documental no están conectados a esta pantalla.',
    future:
      'Farmalidación consultará y versionará la información procedente de CIMA para contrastarla con el maestro, conservando cada versión de forma inmutable.',
    dependency: 'Fase 2 implementada en el backend (DEV-202/205/208); su consumo desde la interfaz es posterior.',
  },
  extraccion: {
    now: 'Los valores mostrados provienen de las fuentes cargadas; no hay ninguna propuesta generada automáticamente.',
    missing: 'La extracción con modelo local no está integrada en esta vertical.',
    future:
      'La extracción automática propondrá valores estructurados a partir de las fuentes documentales. Toda propuesta deberá citar evidencia literal verificable y respetará las reglas de revisión definidas por el proyecto.',
    dependency: 'Fase 4 no abierta: el conjunto oro sigue sin anotar (GOLD-002) y D-014/D-015 siguen pendientes.',
  },
  discrepancias: {
    now: 'Se muestran las diferencias detectadas entre fuentes, conservando todos los valores y su procedencia.',
    missing: 'No existe resolución automática: la matriz de prioridad por campo no está cargada en esta vertical.',
    future:
      'Cuando exista una prioridad aprobada por campo, el sistema indicará qué fuente prevalece y por qué decisión. Mientras tanto, ninguna discrepancia se resuelve sola.',
    dependency: 'ADR-0007 aceptado; la prioridad concreta por campo sigue requiriendo aprobación humana.',
  },
  dobleValidacion: {
    now: 'Se registra una sola firma por decisión, con garantía declarada.',
    missing: 'La segunda validación a ciegas y la conciliación de discrepancias no están implementadas.',
    future:
      'El flujo definitivo incorporará las reglas de revisión y doble validación definidas en las fases posteriores, exigiendo dos revisores distintos para los registros de riesgo.',
    dependency: 'Fase 6; la lista ATC de riesgo adicional a L04 sigue pendiente (D-017).',
  },
  exportacion: {
    now: 'No existe ninguna exportación activa en esta vertical.',
    missing: 'El contrato exacto con el sistema destino no está cerrado.',
    future:
      'La exportación producirá CSV, TXT y XLSX con el orden y los nombres de columna acordados, y ningún registro con discrepancias abiertas podrá exportarse.',
    dependency: 'D-011 (contrato de exportación) y D-012 (separador decimal) siguen pendientes.',
  },
  importaciones: {
    now: 'Los importadores de maestros están implementados y verificados en el backend.',
    missing: 'No existe todavía una pantalla para lanzar y supervisar importaciones.',
    future:
      'Esta sección mostrará los lotes de importación, sus diagnósticos y las filas en cuarentena, sin reparar ningún dato en silencio.',
    dependency: 'Fase 3 cerrada en backend; la interfaz de operación es trabajo posterior.',
  },
  auditoria: {
    now: 'Cada decisión se guarda como evento append-only y su historial se consulta en la ficha.',
    missing: 'No existe una vista transversal de auditoría ni consulta histórica global.',
    future:
      'La auditoría permitirá reconstruir quién decidió qué, cuándo, con qué procedencia y sobre qué versión documental.',
    dependency: 'Fase 6.',
  },
  teclado: {
    now: 'La navegación es con ratón y teclado estándar del navegador.',
    missing: 'Los atajos completos de revisión sin ratón no están implementados.',
    future:
      'Un registro completo podrá validarse sin ratón, con cambio de campo por debajo de 100 ms.',
    dependency: 'DEV-504 y DEV-509, dentro de la Fase 5 todavía no abierta.',
  },
}

/**
 * Aviso permanente sobre el origen de los datos.
 *
 * La demo usa datos de demostración. Decirlo en pantalla es parte de no perder
 * trazabilidad: un dato DEMO no debe poder confundirse con uno importado.
 */
export const DEMO_DATA_NOTICE =
  'Datos de demostración. Los nombres de campo y bloque proceden del catálogo real; ' +
  'los valores no provienen de los maestros ni de CIMA y no deben usarse como evidencia clínica.'
