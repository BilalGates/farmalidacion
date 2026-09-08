"""Cola de revisión: estados, asignación y prevención de colisiones (DEV-502).

Módulo puro: decide qué transición es legítima y quién puede ejecutarla, sin
tocar disco ni red. La persistencia vive en `review_queue_store`, igual que
`validation_states` decide y `review` persiste.

Prioridad: el orden es **técnico**, nunca clínico. Se ordena por prioridad
declarada y antigüedad, porque decidir que un medicamento importa más que otro
es un juicio farmacéutico que este proyecto no puede tomar por su cuenta.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

QueueState = Literal[
    "pendiente",
    "asignado",
    "en_revision",
    "completado",
    "requiere_segunda_revision",
    "bloqueado",
]

OPEN_STATES: frozenset[str] = frozenset(
    {"pendiente", "asignado", "en_revision", "requiere_segunda_revision"}
)
ASSIGNED_STATES: frozenset[str] = frozenset(
    {"asignado", "en_revision", "requiere_segunda_revision"}
)

# Una asignación no puede retener una ficha para siempre: si un revisor cierra
# el navegador, el trabajo debe volver a la cola en lugar de quedar bloqueado.
DEFAULT_LEASE = timedelta(minutes=30)

_ALLOWED: dict[str, frozenset[str]] = {
    "pendiente": frozenset({"asignado", "bloqueado"}),
    "asignado": frozenset({"en_revision", "pendiente", "bloqueado"}),
    "en_revision": frozenset(
        {"completado", "requiere_segunda_revision", "asignado", "pendiente", "bloqueado"}
    ),
    "requiere_segunda_revision": frozenset({"asignado", "completado", "bloqueado"}),
    # Un trabajo completado no se reabre en silencio: vuelve por segunda
    # revisión explícita, que deja rastro de por qué se reabrió.
    "completado": frozenset({"requiere_segunda_revision"}),
    "bloqueado": frozenset({"pendiente"}),
}


class ReviewQueueError(RuntimeError):
    """Transición, asignación o concurrencia no permitida en la cola."""


class QueueConflictError(ReviewQueueError):
    """Dos revisores han intentado avanzar el mismo trabajo a la vez.

    Se distingue de `ReviewQueueError` para que la interfaz pueda ofrecer
    recargar en lugar de presentar un fallo genérico: el trabajo del otro
    revisor no se ha perdido, simplemente llegó antes.
    """


@dataclass(frozen=True)
class QueueItem:
    """Estado observado de un trabajo de la cola.

    `version` implementa bloqueo optimista: quien escribe declara la versión que
    leyó, y si ya no coincide se rechaza en vez de sobrescribir.
    """

    target_record_id: str
    state: QueueState
    version: int
    assignee_id: str | None = None
    assigned_at: datetime | None = None
    priority: int = 0
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.target_record_id:
            raise ValueError("Un trabajo de la cola requiere registro destino.")
        if self.version < 0:
            raise ValueError("La versión no puede ser negativa.")
        if self.state in ASSIGNED_STATES and not self.assignee_id:
            raise ValueError(f"El estado {self.state} exige revisor asignado.")
        if self.state in ("pendiente", "completado", "bloqueado") and self.assignee_id:
            raise ValueError(f"El estado {self.state} no admite revisor asignado.")

    def lease_expired(self, now: datetime, lease: timedelta = DEFAULT_LEASE) -> bool:
        """Una asignación caducada deja de proteger el trabajo."""
        if self.state not in ASSIGNED_STATES or self.assigned_at is None:
            return False
        return now - self.assigned_at > lease


def assert_transition_allowed(current: QueueState, target: QueueState) -> None:
    if current == target:
        return
    allowed = _ALLOWED.get(current, frozenset())
    if target not in allowed:
        raise ReviewQueueError(f"Transición no permitida en la cola: {current} → {target}.")


def assert_version_matches(item: QueueItem, expected_version: int) -> None:
    """Bloqueo optimista: escribir sobre una lectura vieja es un conflicto."""
    if item.version != expected_version:
        raise QueueConflictError(
            "El trabajo ha cambiado desde que se leyó "
            f"(versión {expected_version} frente a {item.version}). Recargue antes de decidir."
        )


def assert_may_act(item: QueueItem, reviewer_id: str, now: datetime,
                   lease: timedelta = DEFAULT_LEASE) -> None:
    """Sólo el asignado actúa, salvo que su asignación haya caducado."""
    if not reviewer_id:
        raise ReviewQueueError("La acción sobre la cola exige revisor identificado.")
    if item.assignee_id is None or item.assignee_id == reviewer_id:
        return
    if item.lease_expired(now, lease):
        return
    raise QueueConflictError(
        f"El trabajo está asignado a {item.assignee_id}; {reviewer_id} no puede modificarlo."
    )


def plan_assignment(item: QueueItem, reviewer_id: str, now: datetime,
                    lease: timedelta = DEFAULT_LEASE) -> QueueItem:
    """Asigna un trabajo, respetando una asignación vigente de otra persona."""
    if not reviewer_id:
        raise ReviewQueueError("Asignar exige revisor identificado.")
    if item.state == "completado":
        raise ReviewQueueError("Un trabajo completado no se asigna sin segunda revisión.")
    if item.state == "bloqueado":
        raise ReviewQueueError("Un trabajo bloqueado debe desbloquearse antes de asignarse.")
    if (
        item.assignee_id is not None
        and item.assignee_id != reviewer_id
        and not item.lease_expired(now, lease)
    ):
        raise QueueConflictError(
            f"El trabajo ya está asignado a {item.assignee_id}."
        )
    if item.state != "requiere_segunda_revision":
        assert_transition_allowed(item.state, "asignado")
    return QueueItem(
        target_record_id=item.target_record_id,
        state="asignado",
        version=item.version + 1,
        assignee_id=reviewer_id,
        assigned_at=now,
        priority=item.priority,
        created_at=item.created_at,
    )


def plan_transition(item: QueueItem, target: QueueState, reviewer_id: str,
                    now: datetime, lease: timedelta = DEFAULT_LEASE) -> QueueItem:
    """Avanza un trabajo comprobando permiso y legitimidad de la transición."""
    assert_may_act(item, reviewer_id, now, lease)
    assert_transition_allowed(item.state, target)
    keeps_assignee = target in ASSIGNED_STATES
    return QueueItem(
        target_record_id=item.target_record_id,
        state=target,
        version=item.version + 1,
        assignee_id=reviewer_id if keeps_assignee else None,
        assigned_at=now if keeps_assignee else None,
        priority=item.priority,
        created_at=item.created_at,
    )


def queue_order(items: tuple[QueueItem, ...]) -> tuple[QueueItem, ...]:
    """Orden técnico reproducible: prioridad, antigüedad y desempate estable.

    No expresa urgencia clínica. `priority` la fija quien configure la carga,
    no una regla de este módulo.
    """
    return tuple(
        sorted(
            items,
            key=lambda i: (
                -i.priority,
                i.created_at.timestamp() if i.created_at else 0.0,
                i.target_record_id,
            ),
        )
    )
