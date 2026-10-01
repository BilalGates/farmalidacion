"""Configuración y comprobación de sólo lectura del Nomenclátor SQL Server."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from importlib import import_module
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool

from pharma_validator_api.models import SourceConnectionConfig, SourceConnectionRevision

router = APIRouter(prefix="/source-connections", tags=["fuentes"])
SOURCE_KEY = "nomenclator"


def get_session(request: Request) -> Iterator[Session]:
    factory = cast(sessionmaker[Session], request.app.state.session_factory)
    with factory() as session:
        yield session


SessionDependency = Annotated[Session, Depends(get_session)]


class ConnectionFields(BaseModel):
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=1433, ge=1, le=65535)
    database_name: str = Field(min_length=1, max_length=128)
    username: str = Field(min_length=1, max_length=128)


class ConnectionWrite(ConnectionFields):
    actor_id: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1, max_length=1000)


class ConnectionTest(ConnectionFields):
    password: SecretStr | None = None


class ConnectionRead(BaseModel):
    configured: bool
    host: str | None
    port: int
    database_name: str | None
    username: str | None
    server_password_configured: bool
    updated_at: str | None


class ConnectionTestResult(BaseModel):
    connected: bool
    database_name: str
    message: str


def _read(row: SourceConnectionConfig | None) -> ConnectionRead:
    return ConnectionRead(
        configured=row is not None,
        host=row.host if row else None,
        port=row.port if row else 1433,
        database_name=row.database_name if row else None,
        username=row.username if row else None,
        server_password_configured=bool(os.environ.get("APP_NOMENCLATOR_PASSWORD")),
        updated_at=row.updated_at.isoformat() if row else None,
    )


@router.get("/nomenclator", response_model=ConnectionRead)
def read_nomenclator(session: SessionDependency) -> ConnectionRead:
    return _read(session.get(SourceConnectionConfig, SOURCE_KEY))


@router.put("/nomenclator", response_model=ConnectionRead)
def save_nomenclator(payload: ConnectionWrite, session: SessionDependency) -> ConnectionRead:
    """Guarda sólo parámetros no secretos y registra actor, motivo y cambio."""
    values = {
        "host": payload.host.strip(),
        "port": payload.port,
        "database_name": payload.database_name.strip(),
        "username": payload.username.strip(),
    }
    if not all((values["host"], values["database_name"], values["username"])):
        raise HTTPException(status_code=422, detail="Complete servidor, base y usuario.")
    actor = payload.actor_id.strip()
    reason = payload.reason.strip()
    if not actor or not reason:
        raise HTTPException(status_code=422, detail="Indique responsable y motivo.")
    row = session.get(SourceConnectionConfig, SOURCE_KEY)
    before = (
        {"host": row.host, "port": row.port, "database_name": row.database_name,
         "username": row.username}
        if row else None
    )
    if before == values:
        return _read(row)
    now = datetime.now(UTC)
    if row is None:
        row = SourceConnectionConfig(source_key=SOURCE_KEY, updated_at=now, **values)
        session.add(row)
    else:
        for key, value in values.items():
            setattr(row, key, value)
        row.updated_at = now
    session.add(SourceConnectionRevision(
        source_key=SOURCE_KEY,
        before_config=json.dumps(before, ensure_ascii=False) if before else None,
        after_config=json.dumps(values, ensure_ascii=False),
        actor_id=actor,
        reason=reason,
        created_at=now,
    ))
    session.commit()
    return _read(row)


def _probe_sql_server(payload: ConnectionTest, password: str) -> str:
    driver = import_module("mssql_python")
    connection = driver.connect(
        server=f"{payload.host.strip()},{payload.port}",
        database=payload.database_name.strip(),
        uid=payload.username.strip(),
        pwd=password,
        encrypt="yes",
        applicationintent="ReadOnly",
        timeout=6,
    )
    try:
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT DB_NAME()")
            result = cursor.fetchone()
            return str(result[0])
        finally:
            cursor.close()
    finally:
        connection.close()


@router.post("/nomenclator/test", response_model=ConnectionTestResult)
async def test_nomenclator(payload: ConnectionTest) -> ConnectionTestResult:
    """Prueba autenticación y SELECT; jamás guarda ni devuelve la contraseña."""
    password = (
        payload.password.get_secret_value() if payload.password else None
    ) or os.environ.get("APP_NOMENCLATOR_PASSWORD")
    if not password:
        raise HTTPException(status_code=422, detail="Indique la contraseña para la prueba.")
    try:
        database_name = await run_in_threadpool(_probe_sql_server, payload, password)
    except Exception:
        raise HTTPException(
            status_code=502,
            detail=(
                "No se pudo conectar a SQL Server o consultar la base. "
                "Compruebe red, TLS y credenciales."
            ),
        ) from None
    return ConnectionTestResult(
        connected=True,
        database_name=database_name,
        message="Conexión de sólo lectura correcta.",
    )
