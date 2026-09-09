import pytest

from pharma_validator_api.pilot_reporting import (
    PilotObservation,
    PilotReportingError,
    build_pilot_report,
)


def observation(record: str, mode: str, **values: object) -> PilotObservation:
    payload: dict[str, object] = {
        "record_id": record,
        "entity_type": "medicamento",
        "mode": mode,
        "minutes": 10 if mode == "manual" else 6,
        "decision_states": ("confirmado",),
    }
    return PilotObservation(**(payload | values))  # type: ignore[arg-type]


def test_complete_report_compares_modes_and_required_metrics() -> None:
    report = build_pilot_report(
        (
            observation("r1", "manual", double_review_count=2, disagreement_count=1),
            observation(
                "r1", "asistida", proposed_count=4, corrected_proposal_count=1
            ),
        ),
        expected_records=1,
    )
    assert report["ready"] is True
    assert report["proposal_correction"] == {
        "proposed": 4,
        "corrected": 1,
        "rate": 0.25,
    }
    assert report["double_review"] == {
        "compared": 2,
        "disagreements": 1,
        "rate": 0.5,
    }
    assert report["minutes_per_record"] == [
        {
            "entity_type": "medicamento",
            "mode": "asistida",
            "record_count": 1,
            "mean_minutes": 6.0,
        },
        {
            "entity_type": "medicamento",
            "mode": "manual",
            "record_count": 1,
            "mean_minutes": 10.0,
        },
    ]


def test_incomplete_report_never_claims_a_result() -> None:
    report = build_pilot_report((observation("r1", "asistida"),), expected_records=1)
    assert report["ready"] is False
    assert report["incomplete_records"] == ["r1"]


def test_empty_denominators_are_unknown_not_zero_rates() -> None:
    report = build_pilot_report((), expected_records=50)
    assert report["ready"] is False
    assert report["proposal_correction"]["rate"] is None  # type: ignore[index]
    assert report["double_review"]["rate"] is None  # type: ignore[index]


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"minutes": -1}, "tiempo"),
        ({"proposed_count": 1, "corrected_proposal_count": 2}, "correcciones"),
        ({"double_review_count": 1, "disagreement_count": 2}, "discrepancias"),
        ({"decision_states": ("pendiente",)}, "Estados"),
    ],
)
def test_inconsistent_observations_are_rejected(
    values: dict[str, object], message: str
) -> None:
    base: dict[str, object] = {
        "record_id": "r1",
        "entity_type": "medicamento",
        "mode": "asistida",
        "minutes": 1,
        "decision_states": (),
    }
    with pytest.raises(PilotReportingError, match=message):
        PilotObservation(**(base | values))  # type: ignore[arg-type]


def test_duplicate_record_and_mode_is_rejected() -> None:
    item = observation("r1", "manual")
    with pytest.raises(PilotReportingError, match="duplicada"):
        build_pilot_report((item, item))
