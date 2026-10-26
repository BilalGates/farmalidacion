"""Manifiesto cerrado por ruta resuelta y método, independiente de la UI."""

from dataclasses import dataclass
from urllib.parse import unquote

from fastapi import HTTPException, Request

from pharma_validator_api.authentication import require_principal
from pharma_validator_api.models import ReviewSession


@dataclass(frozen=True)
class Policy:
    capability: str
    actor_field: str | None = None
    actor_location: str = "json"


POLICIES: dict[tuple[str, str], Policy] = {}


def _rules(method: str, capability: str, paths: tuple[str, ...],
           actor_field: str | None = None, actor_location: str = "json") -> None:
    for path in paths:
        POLICIES[method, path] = Policy(capability, actor_field, actor_location)


_rules("GET", "catalog.read", (
    "/records", "/records/{record_id}",
    "/records/{record_id}/blocks/{block_type}", "/records/{record_id}/block-history",
    "/records/{record_id}/blocks/{block_id}/empty-source-columns",
    "/catalog/identities", "/catalog/identities/{identity_id}",
    "/catalog/identities/{identity_id}/cima-documents",
    "/catalog/identities/{identity_id}/cima-comparison",
    "/catalog/identities/{identity_id}/history", "/catalog/identities/{identity_id}/relations",
    "/catalog/identities/{identity_id}/classifications",
    "/catalog/identities/{identity_id}/classification-history",
    "/nomenclator/identities/{identity_id}/comparison",
    "/insights/dashboard", "/insights/dashboard/explore", "/insights/dashboard/cases",
    "/insights/records", "/insights/records/{record_id}",
    "/risk/rules", "/risk/assess",
))
_rules("POST", "catalog.read", ("/records/{record_id}/chat",))
_rules("POST", "catalog.maintain", (
    "/records/values/{field_value_id}/maintenance", "/catalog/identities",
    "/records/quarantined/{row_id}/empty-source-values",
    "/records/quarantined/{row_id}/values/{source_column_index}/maintenance",
    "/records/{record_id}/blocks/{block_id}/empty-source-values",
), "actor_id")
_rules("POST", "catalog.maintain", ("/records/{record_id}/blocks/{block_type}",), "reviewer_id")
_rules("PUT", "catalog.maintain", (
    "/catalog/identities/{identity_id}",
    "/catalog/identities/{identity_id}/classifications/{classification_id}",
), "actor_id")
_rules("POST", "review.write", (
    "/catalog/identities/{identity_id}/cima-comparisons/{field_value_id}/decisions",
    "/nomenclator/identities/{identity_id}/decisions",
), "actor_id")
_rules("GET", "sources.read", (
    "/records/quarantined", "/records/quarantined/{row_id}/empty-source-columns",
    "/insights/sources", "/insights/sources/{source_id}", "/insights/imports",
    "/insights/imports/{batch_id}", "/maintenance/changes", "/maintenance/changes/history",
    "/maintenance/changes/{event_id}",
    "/maintenance/runs",
))
_rules("GET", "", (
    "/nomenclator/snapshot", "/nomenclator/snapshots",
    "/nomenclator/snapshots/{version_id}/changes",
    "/nomenclator/rows", "/nomenclator/reconciliation",
))
_rules("POST", "", ("/nomenclator/snapshots",))
_rules("PATCH", "sources.manage", ("/insights/sources/{source_id}",), "actor_id")
_rules("POST", "sources.manage", (
    "/imports/master/{kind}/preview", "/source-connections/nomenclator/test", "/maintenance/run",
))
_rules("POST", "sources.manage", ("/imports/master/{kind}",), "x-import-actor", "header")
_rules("GET", "sources.manage", ("/source-connections/nomenclator",))
_rules("PUT", "sources.manage", ("/source-connections/nomenclator",), "actor_id")
_rules("GET", "review.read", ("/queue", "/queue/{target_record_id}"))
_rules("POST", "review.write", ("/queue",))
_rules("POST", "review.write", (
    "/queue/assign-batch", "/queue/next", "/queue/{target_record_id}/assign",
    "/queue/{target_record_id}/transition", "/timing/sessions",
    "/records/values/{field_value_id}/decisions", "/second-reviews/fields/{field_id}",
    "/second-reviews/{assignment_id}/{operation}",
), "reviewer_id")
_rules("POST", "review.write", (
    "/timing/sessions/{session_id}/focus", "/timing/sessions/{session_id}/close",
))
_rules("GET", "review.read", ("/timing/sessions/{session_id}",))
_rules("GET", "review.read", (
    "/second-reviews", "/second-reviews/{assignment_id}/blind",
    "/second-reviews/{assignment_id}/comparison",
), "reviewer_id", "query")
_rules("POST", "export.create", ("/exports",), "actor_id")
_rules("POST", "export.create", ("/master-workbooks/export",))
_rules("GET", "export.read", (
    "/exports", "/exports/{run_id}/exclusions", "/exports/{run_id}/profile",
    "/exports/{run_id}/artifact",
))
_rules("GET", "audit.read", ("/audit/records/{record_id}", "/audit/events"))
_rules("GET", "", ("/records/reviewers",))
_rules("GET", "team.manage", ("/reviewers", "/reviewers/roles"))
_rules("GET", "team.manage", ("/auth/access",))
_rules("POST", "team.manage", ("/reviewers",))
_rules("PUT", "team.manage", ("/reviewers/{identifier}/role", "/reviewers/{identifier}/active"))
_rules("GET", "", ("/database-info", "/maturity"))

PUBLIC_ROUTES = {("GET", "/health"), ("GET", "/ready"),
                 ("GET", "/auth/config"), ("GET", "/auth/me")}


async def authorize(request: Request) -> None:
    if request.app.state.settings.auth_mode == "pilot":
        return
    path = request.scope["route"].path
    if (request.method, path) in PUBLIC_ROUTES:
        return
    principal = await require_principal(request)
    assert principal is not None
    policy = POLICIES.get((request.method, path))
    if policy is None:
        raise HTTPException(403, "Operación sin política de acceso autorizada.")
    capability = policy.capability
    if (path == "/second-reviews/{assignment_id}/{operation}"
            and request.path_params["operation"] == "reconcile"):
        capability = "review.reconcile"
    if capability and capability not in principal.capabilities:
        raise HTTPException(403, "No tienes permiso para esta operación.")
    if policy.actor_field:
        if policy.actor_location == "json":
            try:
                body = await request.json()
            except ValueError as error:
                raise HTTPException(422, "La solicitud debe contener un objeto JSON.") from error
            if not isinstance(body, dict):
                raise HTTPException(422, "La solicitud debe contener un objeto JSON.")
            supplied = body.get(policy.actor_field)
            if (path.endswith("/cima-comparisons/{field_value_id}/decisions")
                    and body.get("action") == "corregir"
                    and "catalog.maintain" not in principal.capabilities):
                raise HTTPException(403, "No tienes permiso para corregir el catálogo.")
        else:
            source = request.headers if policy.actor_location == "header" else request.query_params
            values = source.getlist(policy.actor_field)
            supplied = values[0] if len(values) == 1 else None
            if policy.actor_location == "header" and isinstance(supplied, str):
                supplied = unquote(supplied)
        if supplied != principal.reviewer.identifier:
            raise HTTPException(403, "La identidad indicada no coincide con la sesión.")
    if (path == "/catalog/identities" and request.query_params.get("review_scope") == "mine"
            and request.query_params.getlist("reviewer_id") != [principal.reviewer.identifier]):
        raise HTTPException(403, "La identidad indicada no coincide con la sesión.")
    if path.startswith("/timing/sessions/"):
        with request.app.state.session_factory() as session:
            row = session.get(ReviewSession, request.path_params["session_id"])
            if row is None:
                raise HTTPException(404, "Sesión de medición no encontrada.")
            if row.reviewer_id != principal.reviewer.identifier:
                raise HTTPException(403, "Esta sesión de medición pertenece a otra cuenta.")
