# Dependencias externas abiertas tras Gate 0B

## PROVIDER-001 — Semántica de `S*` / `N*`

- Abierta; no bloquea Fase 1. Resolver antes de reglas definitivas de obligatoriedad condicional.
- Conservar literal `S`, `N`, `S*`, `N*`.
- Solo derivar `S`/`S*` → `base_required=true` y `N`/`N*` → `base_required=false`.
- Asterisco: `modifier_semantics=unresolved`; ninguna regla definitiva depende de él.

## PROVIDER-002 — Serialización de `no_consta` / `no_aplica`

- Abierta; no bloquea Fase 1. Resolver antes del contrato/exportador definitivo.
- Estados internos explícitos y diferentes.
- No presumir `NULL`, vacío, omisión, sentinela, código ni otra representación.
- Sin contrato confirmado, una salida productiva falla; nunca inventa traducción.

La excepción humana de Gate 0B autoriza el scaffold, no las funcionalidades bloqueadas.
