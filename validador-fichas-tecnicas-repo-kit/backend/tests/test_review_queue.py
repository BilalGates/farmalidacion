"""Cola de revisión: transiciones, asignación y colisiones (DEV-502)."""

from datetime import UTC, datetime, timedelta

import pytest

from pharma_validator_api.review_queue import (
    DEFAULT_LEASE,
    QueueConflictError,
    QueueItem,
    ReviewQueueError,
    assert_transition_allowed,
    assert_version_matches,
    plan_assignment,
    plan_transition,
    queue_order,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


def pending(record_id: str = "rec-1", **kwargs: object) -> QueueItem:
    return QueueItem(target_record_id=record_id, state="pendiente", version=1, **kwargs)  # type: ignore[arg-type]


def assigned(reviewer: str = "rev-a", at: datetime = NOW) -> QueueItem:
    return QueueItem(
        target_record_id="rec-1",
        state="asignado",
        version=2,
        assignee_id=reviewer,
        assigned_at=at,
    )


def test_an_assigned_state_requires_a_reviewer() -> None:
    """Un trabajo asignado sin revisor sería un trabajo que nadie ha tomado."""
    with pytest.raises(ValueError):
        QueueItem(target_record_id="rec-1", state="asignado", version=1)


def test_a_pending_state_rejects_a_reviewer() -> None:
    with pytest.raises(ValueError):
        QueueItem(
            target_record_id="rec-1", state="pendiente", version=1, assignee_id="rev-a"
        )


def test_completed_work_does_not_reopen_silently() -> None:
    """Reabrir sin rastro borraría por qué se dio por bueno."""
    with pytest.raises(ReviewQueueError):
        assert_transition_allowed("completado", "en_revision")
    assert_transition_allowed("completado", "requiere_segunda_revision")


def test_a_stale_read_is_a_conflict_not_an_overwrite() -> None:
    item = QueueItem(target_record_id="rec-1", state="pendiente", version=5)
    assert_version_matches(item, 5)
    with pytest.raises(QueueConflictError):
        assert_version_matches(item, 4)


def test_a_second_reviewer_cannot_steal_live_work() -> None:
    """El caso que motiva el bloqueo: dos revisores sobre la misma ficha."""
    item = assigned("rev-a")
    with pytest.raises(QueueConflictError):
        plan_assignment(item, "rev-b", NOW + timedelta(minutes=1))


def test_an_expired_lease_returns_work_to_the_queue() -> None:
    """Si un revisor cierra el navegador, la ficha no queda retenida."""
    item = assigned("rev-a", at=NOW)
    later = NOW + DEFAULT_LEASE + timedelta(minutes=1)
    assert item.lease_expired(later)
    taken = plan_assignment(item, "rev-b", later)
    assert taken.assignee_id == "rev-b"
    assert taken.version == item.version + 1


def test_assignment_increments_the_version() -> None:
    taken = plan_assignment(pending(), "rev-a", NOW)
    assert (taken.state, taken.assignee_id, taken.version) == ("asignado", "rev-a", 2)


def test_completing_clears_the_assignee() -> None:
    """Un trabajo completado no sigue ocupando a nadie."""
    started = plan_transition(assigned("rev-a"), "en_revision", "rev-a", NOW)
    done = plan_transition(started, "completado", "rev-a", NOW)
    assert done.state == "completado"
    assert done.assignee_id is None


def test_a_foreign_reviewer_cannot_advance_someone_elses_work() -> None:
    with pytest.raises(QueueConflictError):
        plan_transition(assigned("rev-a"), "en_revision", "rev-b", NOW)


def test_blocked_work_must_be_unblocked_before_assignment() -> None:
    blocked = QueueItem(target_record_id="rec-1", state="bloqueado", version=3)
    with pytest.raises(ReviewQueueError):
        plan_assignment(blocked, "rev-a", NOW)
    assert_transition_allowed("bloqueado", "pendiente")


def test_second_review_can_be_assigned_without_reopening_as_pending() -> None:
    item = QueueItem(
        target_record_id="rec-1",
        state="requiere_segunda_revision",
        version=4,
        assignee_id="rev-a",
        assigned_at=NOW,
    )
    taken = plan_assignment(item, "rev-b", NOW + timedelta(hours=2))
    assert (taken.state, taken.assignee_id) == ("asignado", "rev-b")


def test_order_is_technical_and_reproducible() -> None:
    """Prioridad declarada y antigüedad; nunca urgencia clínica inventada."""
    old = NOW - timedelta(days=1)
    items = (
        pending("rec-b", priority=0, created_at=NOW),
        pending("rec-c", priority=5, created_at=NOW),
        pending("rec-a", priority=0, created_at=old),
    )
    assert [i.target_record_id for i in queue_order(items)] == ["rec-c", "rec-a", "rec-b"]
    assert queue_order(items) == queue_order(tuple(reversed(items)))
