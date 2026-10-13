"""Acceso Entra de un tenant, con permisos y actor comprobados en servidor.

No admite ID tokens, tokens de Graph ni identidades aportadas por el navegador.
El modo piloto sigue siendo declarado. Configuración ausente cierra el acceso
corporativo, sin degradar a piloto ni cambiar la garantía de firmas históricas.
"""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

import jwt
from fastapi import APIRouter, HTTPException, Request
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from pharma_validator_api.config import Settings
from pharma_validator_api.models import AuthIdentityBinding, ReviewerRecord
from pharma_validator_api.reviewer_identity import ROLE_LABELS, Reviewer, ReviewerDirectory
from pharma_validator_api.validation_states import ReviewerRole

CAPABILITIES = frozenset({
    "catalog.read", "catalog.maintain", "sources.read", "sources.manage",
    "review.read", "review.write", "review.reconcile", "export.read", "export.create",
    "audit.read", "team.manage",
})


def configured(settings: Settings) -> bool:
    try:
        for value in (settings.entra_tenant_id, settings.entra_api_client_id,
                      settings.entra_spa_client_id, *settings.entra_reviewer_bindings):
            if str(UUID(value)) != value:
                return False
    except (ValueError, TypeError):
        return False
    bindings = settings.entra_reviewer_bindings
    matrix = settings.entra_role_capabilities
    return bool(
        bindings and len(set(bindings.values())) == len(bindings)
        and all(handle.strip() == handle and 0 < len(handle) <= 80 for handle in bindings.values())
        and matrix and all(role and caps and set(caps) <= CAPABILITIES
                           for role, caps in matrix.items())
        and settings.entra_required_scope and " " not in settings.entra_required_scope
        and settings.entra_spa_scope.endswith("/" + settings.entra_required_scope)
    )


@dataclass(frozen=True)
class Principal:
    subject_id: str
    reviewer: Reviewer
    capabilities: frozenset[str]


class EntraVerifier:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.issuer = f"https://login.microsoftonline.com/{settings.entra_tenant_id}/v2.0"
        self.keys = PyJWKClient(
            f"https://login.microsoftonline.com/{settings.entra_tenant_id}/discovery/v2.0/keys",
            timeout=5, lifespan=300,
        )

    def verify(self, token: str) -> dict[str, Any]:
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
                raise jwt.InvalidTokenError()
            key = self.keys.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token, key, algorithms=["RS256"],
                audience=self.settings.entra_api_client_id, issuer=self.issuer,
                options={"require": ["exp", "nbf", "iat", "iss", "aud", "tid", "oid",
                                     "sub", "ver", "azp", "scp"]},
            )
            if (claims["ver"] != "2.0" or claims["tid"] != self.settings.entra_tenant_id
                    or claims["azp"] != self.settings.entra_spa_client_id
                    or not isinstance(claims["scp"], str)
                    or self.settings.entra_required_scope not in claims["scp"].split()
                    or str(UUID(claims["oid"])) != claims["oid"]):
                raise jwt.InvalidTokenError()
            return cast(dict[str, Any], claims)
        except PyJWKClientConnectionError as error:
            raise HTTPException(503, "No se puede verificar la sesión corporativa.") from error
        except (jwt.PyJWTError, ValueError, TypeError, KeyError) as error:
            raise HTTPException(401, "Sesión inválida o caducada.",
                                headers={"WWW-Authenticate": "Bearer"}) from error


async def require_principal(request: Request) -> Principal | None:
    settings: Settings = request.app.state.settings
    if settings.auth_mode == "pilot":
        return None
    existing = getattr(request.state, "principal", None)
    if existing is not None:
        return cast(Principal, existing)
    if not configured(settings):
        raise HTTPException(503, "El acceso corporativo está pendiente de configuración.")
    values = request.headers.getlist("authorization")
    if len(values) != 1 or not values[0].startswith("Bearer "):
        raise HTTPException(401, "Inicia sesión para acceder.",
                            headers={"WWW-Authenticate": "Bearer"})
    token = values[0][7:]
    if not token or len(token) > 32000:
        raise HTTPException(401, "Sesión inválida.")
    claims = await run_in_threadpool(request.app.state.entra_verifier.verify, token)
    roles = claims.get("roles", [])
    if not isinstance(roles, list) or not all(isinstance(role, str) for role in roles):
        raise HTTPException(403, "La cuenta no tiene permisos para esta aplicación.")
    caps = frozenset(cap for role in roles
                     for cap in settings.entra_role_capabilities.get(role, ()))
    actor = settings.entra_reviewer_bindings.get(claims["oid"])
    if not caps or actor is None:
        raise HTTPException(403, "La cuenta no tiene permisos para esta aplicación.")
    with request.app.state.session_factory() as session:
        row = session.scalar(select(ReviewerRecord).where(ReviewerRecord.identifier == actor))
        if row is not None:
            if not row.active:
                raise HTTPException(403, "Tu acceso ha sido desactivado.")
            reviewer = Reviewer(actor, row.display_name, cast(ReviewerRole, row.role))
        elif session.scalar(select(ReviewerRecord.id).limit(1)) is not None:
            raise HTTPException(403, "La cuenta no tiene un revisor autorizado.")
        else:
            directory = ReviewerDirectory.from_configuration(settings.reviewers)
            candidate = next(
                (item for item in directory.reviewers if item.identifier == actor), None
            )
            if candidate is None:
                raise HTTPException(403, "La cuenta no tiene un revisor autorizado.")
            reviewer = candidate
        links = session.scalars(select(AuthIdentityBinding).where(or_(
            AuthIdentityBinding.reviewer_identifier == actor,
            (AuthIdentityBinding.tenant_id == claims["tid"])
            & (AuthIdentityBinding.object_id == claims["oid"]),
        ))).all()
        if links:
            if any(link.tenant_id != claims["tid"] or link.object_id != claims["oid"]
                   or link.reviewer_identifier != actor for link in links):
                raise HTTPException(403, "El vínculo de identidad no puede reasignarse.")
        else:
            session.add(AuthIdentityBinding(tenant_id=claims["tid"], object_id=claims["oid"],
                                           reviewer_identifier=actor, created_at=datetime.now(UTC)))
            try:
                session.commit()
            except IntegrityError as error:
                session.rollback()
                raise HTTPException(409, "El vínculo de identidad requiere revisión.") from error
    principal = Principal(f"entra:{claims['tid']}:{claims['oid']}",
                          replace(reviewer, assurance="verificada_entra"), caps)
    request.state.principal = principal
    return principal


router = APIRouter(prefix="/auth", tags=["acceso"])


@router.get("/config")
def auth_config(request: Request) -> dict[str, Any]:
    settings: Settings = request.app.state.settings
    ready = settings.auth_mode == "entra" and configured(settings)
    return {
        "mode": settings.auth_mode, "configured": ready,
        "tenant_id": settings.entra_tenant_id if ready else None,
        "spa_client_id": settings.entra_spa_client_id if ready else None,
        "scope": settings.entra_spa_scope if ready else None,
    }


@router.get("/me")
async def current_user(request: Request) -> dict[str, Any]:
    principal = await require_principal(request)
    if principal is None:
        raise HTTPException(409, "Este entorno usa identificación declarada del piloto.")
    reviewer = principal.reviewer
    return {
        "subject_id": principal.subject_id, "capabilities": sorted(principal.capabilities),
        "reviewer": {"identifier": reviewer.identifier, "display_name": reviewer.display_name,
                     "role": reviewer.role, "role_label": ROLE_LABELS[reviewer.role],
                     "assurance": reviewer.assurance,
                     "may_sign_pharmacist_states": reviewer.may_sign_pharmacist_states},
    }


@router.get("/access")
async def access_overview(request: Request) -> dict[str, Any]:
    """Asignaciones efectivas para administración; nunca expone tokens ni secretos."""
    principal = await require_principal(request)
    if principal is None:
        raise HTTPException(409, "El piloto no tiene cuentas corporativas.")
    settings: Settings = request.app.state.settings
    with request.app.state.session_factory() as session:
        reviewers = {
            row.identifier: row for row in session.scalars(select(ReviewerRecord)).all()
        }
        linked = {
            (row.object_id, row.reviewer_identifier)
            for row in session.scalars(select(AuthIdentityBinding)).all()
        }
    directory = ReviewerDirectory.from_configuration(settings.reviewers)
    configured_reviewers = {row.identifier: row for row in directory.reviewers}
    def account_name(handle: str) -> str:
        row = reviewers.get(handle) or configured_reviewers.get(handle)
        return row.display_name if row else handle

    def account_active(handle: str) -> bool:
        row = reviewers.get(handle) if reviewers else configured_reviewers.get(handle)
        return bool(row and getattr(row, "active", True))

    return {
        "roles": [
            {"name": name, "capabilities": sorted(capabilities)}
            for name, capabilities in sorted(settings.entra_role_capabilities.items())
        ],
        "accounts": [
            {
                "object_id": object_id,
                "reviewer_identifier": handle,
                "display_name": account_name(handle),
                "active": account_active(handle),
                "linked": (object_id, handle) in linked,
            }
            for object_id, handle in sorted(settings.entra_reviewer_bindings.items(),
                                            key=lambda item: item[1])
        ],
    }
