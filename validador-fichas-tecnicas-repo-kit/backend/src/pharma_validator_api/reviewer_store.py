"""Lista de revisores persistida (10.1, D-018).

Los revisores vivían en `APP_REVIEWERS`, de modo que dar de alta a alguien
exigía editar el despliegue y reiniciar el contenedor. Aquí son datos, y la
lista se gestiona desde la aplicación.

Dos reglas que no son negociables y por eso viven aquí y no en el endpoint:

- **Nadie se borra.** Una decisión firmada debe seguir diciendo quién la puso;
  eliminar la fila dejaría el historial apuntando a un revisor inexistente.
  Desactivar retira del selector sin tocar el pasado.
- **El identificador no se reutiliza.** Es lo que enlaza una firma con quien la
  hizo: reasignarlo a otra persona reescribiría el pasado en silencio.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_validator_api.models import ReviewerRecord
from pharma_validator_api.reviewer_identity import (
    ROLE_LABELS,
    Reviewer,
    ReviewerDirectory,
    ReviewerIdentityError,
)


def list_reviewers(session: Session, *, include_inactive: bool = False) -> list[ReviewerRecord]:
    """Revisores por nombre. Los inactivos sólo si se piden explícitamente."""
    statement = select(ReviewerRecord).order_by(ReviewerRecord.display_name)
    if not include_inactive:
        statement = statement.where(ReviewerRecord.active.is_(True))
    return list(session.scalars(statement).all())


def directory_from_database(session: Session) -> ReviewerDirectory:
    """Directorio con los revisores activos.

    Sólo los activos pueden firmar: un revisor desactivado conserva sus firmas
    anteriores pero no puede añadir nuevas, que es justo lo que significa
    desactivarlo.
    """
    return ReviewerDirectory(
        tuple(
            Reviewer(row.identifier, row.display_name, row.role)  # type: ignore[arg-type]
            for row in list_reviewers(session)
        )
    )


def create_reviewer(
    session: Session, *, identifier: str, display_name: str, role: str
) -> ReviewerRecord:
    """Da de alta un revisor.

    Un identificador ya usado se rechaza aunque su revisor esté desactivado:
    reutilizarlo haría que las firmas antiguas pareciesen de la persona nueva.
    """
    identifier = identifier.strip()
    display_name = display_name.strip()
    if not identifier:
        raise ReviewerIdentityError("El revisor requiere identificador.")
    if not display_name:
        raise ReviewerIdentityError("El revisor requiere nombre visible.")
    if role not in ROLE_LABELS:
        raise ReviewerIdentityError(f"Rol de revisor no reconocido: {role!r}")
    existing = session.scalar(select(ReviewerRecord).where(ReviewerRecord.identifier == identifier))
    if existing is not None:
        raise ReviewerIdentityError(
            f"El identificador {identifier!r} ya está en uso y no puede reasignarse."
        )
    record = ReviewerRecord(
        identifier=identifier,
        display_name=display_name,
        role=role,
        active=True,
        created_at=datetime.now(UTC),
    )
    session.add(record)
    session.flush()
    return record


def set_reviewer_active(session: Session, identifier: str, active: bool) -> ReviewerRecord:
    """Activa o desactiva un revisor, conservando su historial intacto."""
    record = session.scalar(select(ReviewerRecord).where(ReviewerRecord.identifier == identifier))
    if record is None:
        raise ReviewerIdentityError(f"El revisor {identifier!r} no existe.")
    if not active and _would_leave_no_pharmacist(session, record):
        # Sin farmacéutico activo nadie podría declarar `no_consta` ni
        # `no_aplica`: la aplicación quedaría sin poder cerrar esos campos.
        raise ReviewerIdentityError(
            "No se puede desactivar al último farmacéutico activo: "
            "nadie podría declarar «no consta» ni «no aplica»."
        )
    record.active = active
    session.flush()
    return record


def update_reviewer_role(session: Session, identifier: str, role: str) -> ReviewerRecord:
    """Cambia el rol de un revisor.

    No reescribe las firmas ya puestas: el rol con que se firmó queda en cada
    decisión, porque es parte de lo que se firmó.
    """
    if role not in ROLE_LABELS:
        raise ReviewerIdentityError(f"Rol de revisor no reconocido: {role!r}")
    record = session.scalar(select(ReviewerRecord).where(ReviewerRecord.identifier == identifier))
    if record is None:
        raise ReviewerIdentityError(f"El revisor {identifier!r} no existe.")
    if role != "farmaceutico" and _would_leave_no_pharmacist(session, record):
        raise ReviewerIdentityError(
            "No se puede cambiar el rol del último farmacéutico activo: "
            "nadie podría declarar «no consta» ni «no aplica»."
        )
    record.role = role
    session.flush()
    return record


def _would_leave_no_pharmacist(session: Session, record: ReviewerRecord) -> bool:
    """Si retirar a este revisor dejaría la lista sin farmacéutico activo."""
    if record.role != "farmaceutico" or not record.active:
        return False
    otros = session.scalars(
        select(ReviewerRecord)
        .where(ReviewerRecord.role == "farmaceutico")
        .where(ReviewerRecord.active.is_(True))
        .where(ReviewerRecord.identifier != record.identifier)
    ).all()
    return not otros
