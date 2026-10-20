"""Tokens sintéticos firmados y una base desechable; sin cuentas ni red reales."""

import json
import time
from types import SimpleNamespace

import jwt
import pytest
from conftest import seed_reviewable_record
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt.exceptions import PyJWKClientConnectionError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pharma_validator_api.access_policy import POLICIES, PUBLIC_ROUTES
from pharma_validator_api.authentication import CAPABILITIES
from pharma_validator_api.config import Settings
from pharma_validator_api.main import create_app
from pharma_validator_api.models import (
    AuditEvent,
    AuthIdentityBinding,
    ImmutableHistoryError,
    ValidationDecisionRecord,
)

TENANT = "11111111-1111-1111-1111-111111111111"
API = "22222222-2222-2222-2222-222222222222"
SPA = "33333333-3333-3333-3333-333333333333"
ANA = "44444444-4444-4444-4444-444444444444"
LUIS = "55555555-5555-5555-5555-555555555555"
OTHER = "66666666-6666-6666-6666-666666666666"
FIELD = "fv-rec-1-1-0"


@pytest.fixture(scope="module")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def corporate(scratch_db_url, signing_key):
    engine = create_engine(scratch_db_url)
    with Session(engine) as session:
        seed_reviewable_record(session)
    engine.dispose()
    settings = Settings(
        database_url=scratch_db_url, data_mode="real", auth_mode="entra",
        reviewers=("ana:Ana:farmaceutico", "luis:Luis:tecnico"),
        entra_tenant_id=TENANT, entra_api_client_id=API, entra_spa_client_id=SPA,
        entra_spa_scope=f"api://{API}/access_as_user",
        entra_role_capabilities={"Reader": ("catalog.read",), "Admin": tuple(CAPABILITIES)},
        entra_reviewer_bindings={ANA: "ana", LUIS: "luis"}, enable_second_review=True,
    )
    app = create_app(settings)
    app.state.entra_verifier.keys = SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=signing_key.public_key())
    )
    return TestClient(app), settings


def token(key, **changes):
    now = int(time.time())
    claims = dict(iss=f"https://login.microsoftonline.com/{TENANT}/v2.0", aud=API,
                  tid=TENANT, oid=ANA, sub="synthetic-subject", azp=SPA, ver="2.0",
                  scp="access_as_user", roles=["Admin"], iat=now - 5, nbf=now - 5, exp=now + 300)
    claims.update(changes)
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test-key"})


def auth(key, **changes):
    return {"Authorization": "Bearer " + token(key, **changes)}


def test_every_operation_has_an_explicit_policy(corporate):
    client, _ = corporate
    operations = {(method.upper(), path)
                  for path, methods in client.app.openapi()["paths"].items()
                  for method in methods if method != "parameters"}
    assert operations == set(POLICIES) | PUBLIC_ROUTES


def test_no_token_cannot_read_or_download_and_health_remains_public(corporate):
    client, _ = corporate
    for path in ("/records", "/database-info", "/exports/run/artifact", "/reviewers"):
        assert client.get(path).status_code == 401
    assert client.get("/health").status_code == 200
    assert client.get("/auth/config").json()["configured"] is True


def test_every_signed_in_role_can_access_personal_nomenclator_routes(
    corporate, signing_key,
):
    client, _ = corporate
    reader = auth(signing_key, roles=["Reader"])
    assert client.get("/nomenclator/snapshot").status_code == 401
    assert client.post("/nomenclator/snapshots", content=b"test").status_code == 401
    assert client.get("/nomenclator/snapshot", headers=reader).status_code == 200
    # El almacenamiento no está configurado en esta prueba. El 503 demuestra
    # que el lector atravesó la autorización hasta el controlador de la ruta.
    assert client.post(
        "/nomenclator/snapshots", headers=reader, content=b"test",
    ).status_code == 503


def test_reader_can_see_team_without_managing_it(corporate, signing_key):
    client, _ = corporate
    reader = auth(signing_key, roles=["Reader"])
    assert client.get("/records/reviewers").status_code == 401
    response = client.get("/records/reviewers", headers=reader)
    assert response.status_code == 200
    assert {item["identifier"] for item in response.json()} >= {"ana", "luis"}
    assert client.get("/reviewers", headers=reader).status_code == 403
    assert client.post(
        "/reviewers", headers=reader,
        json={"identifier": "otro", "display_name": "Otro", "role": "tecnico"},
    ).status_code == 403


@pytest.mark.parametrize("changes", [
    {"aud": "https://graph.microsoft.com"}, {"iss": "https://invalid.example"},
    {"tid": OTHER}, {"azp": OTHER}, {"exp": 1}, {"nbf": 9999999999},
    {"ver": "1.0"}, {"scp": "other"}, {"oid": "not-a-guid"}, {"scp": None},
])
def test_invalid_claims_are_rejected(corporate, signing_key, changes):
    client, _ = corporate
    assert client.get("/records", headers=auth(signing_key, **changes)).status_code == 401


def test_signature_cannot_be_forged(corporate):
    client, _ = corporate
    forged = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert client.get("/records", headers=auth(forged)).status_code == 401


@pytest.mark.parametrize("changes", [{"roles": []}, {"roles": ["Unknown"]}, {"oid": OTHER}])
def test_unassigned_accounts_are_rejected(corporate, signing_key, changes):
    client, _ = corporate
    assert client.get("/auth/me", headers=auth(signing_key, **changes)).status_code == 403


def test_permissions_are_checked_by_server(corporate, signing_key):
    client, _ = corporate
    headers = auth(signing_key, roles=["Reader"])
    assert client.get("/records", headers=headers).status_code == 200
    assert client.get("/reviewers", headers=headers).status_code == 403
    assert client.get("/reviewers/roles", headers=headers).status_code == 403
    assert client.get("/auth/access", headers=headers).status_code == 403
    assert client.get("/exports/x/artifact", headers=headers).status_code == 403
    response = client.post("/queue", headers=headers, json={"target_record_id": "rec-1"})
    assert response.status_code == 403


def test_administrator_can_inspect_roles_and_account_bindings(corporate, signing_key):
    client, _ = corporate
    response = client.get("/auth/access", headers=auth(signing_key))
    assert response.status_code == 200, response.text
    data = response.json()
    reader = next(role for role in data["roles"] if role["name"] == "Reader")
    assert reader["capabilities"] == ["catalog.read"]
    ana = next(account for account in data["accounts"] if account["reviewer_identifier"] == "ana")
    assert ana["object_id"] == ANA
    assert ana["active"] is True
    assert ana["linked"] is True
    assert "token" not in response.text.lower()


def test_actors_in_body_query_and_upload_header_cannot_be_spoofed(corporate, signing_key):
    client, _ = corporate
    headers = auth(signing_key)
    response = client.post(f"/records/values/{FIELD}/decisions", headers=headers,
                           json={"reviewer_id": "luis", "state": "confirmado"})
    assert response.status_code == 403
    assert client.get("/second-reviews?reviewer_id=luis", headers=headers).status_code == 403
    assert client.get("/second-reviews?reviewer_id=ana&reviewer_id=luis",
                      headers=headers).status_code == 403
    assert client.get("/catalog/identities?review_scope=mine&reviewer_id=luis",
                      headers=headers).status_code == 403
    upload = {**headers, "X-Import-Actor": "luis", "Content-Type": "application/octet-stream"}
    assert client.post("/imports/master/medicamentos", headers=upload,
                       content=b"not an Excel").status_code == 403
    assert client.put("/source-connections/nomenclator", headers=headers,
                      json={"actor_id": "luis"}).status_code == 403


def test_verification_applies_only_to_new_actor_events(corporate, signing_key):
    client, settings = corporate
    response = client.post(f"/records/values/{FIELD}/decisions", headers=auth(signing_key),
                           json={"reviewer_id": "ana", "state": "confirmado",
                                 "final_value": "ácido nicotínico"})
    assert response.status_code == 201, response.text
    assert response.json()["reviewer_assurance"] == "verificada_entra"
    reviewers = client.get("/records/reviewers", headers=auth(signing_key)).json()
    assert next(row for row in reviewers if row["identifier"] == "luis")["assurance"] == "declarada"
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        assert session.scalar(select(ValidationDecisionRecord)).reviewer_id == "ana"
        assert session.scalar(select(AuthIdentityBinding)).object_id == ANA
    engine.dispose()


def test_bindings_cannot_reassign_history(corporate, signing_key):
    client, settings = corporate
    assert client.get("/auth/me", headers=auth(signing_key)).status_code == 200
    settings.entra_reviewer_bindings = {OTHER: "ana", LUIS: "luis"}
    assert client.get("/auth/me", headers=auth(signing_key, oid=OTHER)).status_code == 403


def test_timing_sessions_are_private_to_owner(corporate, signing_key):
    client, _ = corporate
    headers = auth(signing_key)
    opened = client.post("/timing/sessions", headers=headers,
                         json={"target_record_id": "rec-1", "reviewer_id": "ana"})
    assert opened.status_code == 201, opened.text
    session_id = opened.json()["id"]
    other = auth(signing_key, oid=LUIS)
    assert client.get(f"/timing/sessions/{session_id}", headers=other).status_code == 403
    assert client.post(f"/timing/sessions/{session_id}/close", headers=other).status_code == 403
    assert client.post(f"/timing/sessions/{session_id}/focus", headers=other,
                       json={"field_name": "DESCRIPCION", "started_at": "2026-10-05T10:00:00Z",
                             "ended_at": "2026-10-05T10:00:01Z"}).status_code == 403
    assert client.get(f"/timing/sessions/{session_id}", headers=headers).status_code == 200


def test_missing_config_and_unreachable_keys_fail_closed(scratch_db_url, corporate, signing_key):
    unconfigured = TestClient(create_app(Settings(database_url=scratch_db_url, auth_mode="entra")))
    assert unconfigured.get("/auth/config").json()["configured"] is False
    assert unconfigured.get("/records").status_code == 503
    client, _ = corporate
    def unavailable(token):
        raise PyJWKClientConnectionError("synthetic outage")
    client.app.state.entra_verifier.keys = SimpleNamespace(get_signing_key_from_jwt=unavailable)
    assert client.get("/records", headers=auth(signing_key)).status_code == 503


def test_unknown_new_route_fails_closed(corporate, signing_key):
    client, _ = corporate
    @client.app.get("/future-data")
    def future():
        return {"hidden": True}
    assert client.get("/future-data", headers=auth(signing_key)).status_code == 403


def test_second_reading_cannot_upgrade_technical_role(corporate, signing_key):
    client, _ = corporate
    first = client.post(f"/records/values/{FIELD}/decisions", headers=auth(signing_key),
                        json={"reviewer_id": "ana", "state": "confirmado",
                              "final_value": "ácido nicotínico"})
    assert first.status_code == 201
    opened = client.post(f"/second-reviews/fields/{FIELD}", headers=auth(signing_key),
                         json={"reviewer_id": "ana"})
    assert opened.status_code == 201
    assignment = opened.json()["id"]
    technical = auth(signing_key, oid=LUIS)
    response = client.post(f"/second-reviews/{assignment}/decisions", headers=technical,
                           json={"reviewer_id": "luis", "state": "no_aplica",
                                 "comment": "No corresponde a este registro."})
    assert response.status_code == 400
    assert "farmac" in response.json()["detail"]


def test_second_reading_audit_keeps_verified_assurance(corporate, signing_key):
    client, settings = corporate
    assert client.post(f"/records/values/{FIELD}/decisions", headers=auth(signing_key),
                       json={"reviewer_id": "ana", "state": "confirmado",
                             "final_value": "ácido nicotínico"}).status_code == 201
    opened = client.post(f"/second-reviews/fields/{FIELD}", headers=auth(signing_key),
                         json={"reviewer_id": "ana"})
    base = "/second-reviews/" + opened.json()["id"]
    headers = auth(signing_key, oid=LUIS)
    assert client.post(base + "/claim", headers=headers,
                       json={"reviewer_id": "luis"}).status_code == 200
    assert client.post(base + "/decisions", headers=headers,
                       json={"reviewer_id": "luis", "state": "confirmado",
                             "final_value": "ácido nicotínico"}).status_code == 200
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        events = session.scalars(select(AuditEvent).where(
            AuditEvent.action.in_(("segunda_revision_abierta", "segunda_revision_reclamada",
                                  "segunda_revision_emitida"))
        )).all()
        assert len(events) == 3
        assert {event.actor_assurance for event in events} == {"verificada_entra"}
    engine.dispose()


def test_existing_binding_cannot_be_changed_or_deleted(corporate, signing_key):
    client, settings = corporate
    assert client.get("/auth/me", headers=auth(signing_key)).status_code == 200
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        link = session.scalar(select(AuthIdentityBinding))
        link.object_id = OTHER
        with pytest.raises(ImmutableHistoryError):
            session.commit()
        session.rollback()
        session.delete(link)
        with pytest.raises(ImmutableHistoryError):
            session.commit()
        session.rollback()
    engine.dispose()


def test_jwks_rotation_refreshes_unknown_key_without_accepting_bad_signature(
    corporate, signing_key
):
    client, _ = corporate
    verifier = client.app.state.entra_verifier
    previous = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(signing_key.public_key()))
    previous.update(kid="test-key", use="sig", alg="RS256")
    replacement = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    current = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(replacement.public_key()))
    current.update(kid="rotated-key", use="sig", alg="RS256")
    keys = jwt.PyJWKClient(f"https://login.microsoftonline.com/{TENANT}/discovery/v2.0/keys")
    keys.jwk_set_cache.put({"keys": [previous]})
    fetches = []
    def fetch_keys():
        fetches.append(True)
        return {"keys": [current]}
    keys.fetch_data = fetch_keys
    verifier.keys = keys
    assert client.get("/auth/me", headers=auth(signing_key)).status_code == 200
    claims = jwt.decode(token(replacement), options={"verify_signature": False})
    rotated = jwt.encode(claims, replacement, algorithm="RS256", headers={"kid": "rotated-key"})
    assert client.get("/auth/me", headers={"Authorization": "Bearer " + rotated}).status_code == 200
    assert len(fetches) == 1
