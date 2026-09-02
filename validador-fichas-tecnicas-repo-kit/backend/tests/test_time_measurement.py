import pytest

from pharma_validator_api.time_measurement import (
    INACTIVITY_THRESHOLD_SECONDS,
    FocusInterval,
    TimeMeasurementError,
    measure_field,
    measure_session,
)


def test_a_single_focus_interval_counts_whole() -> None:
    timing = measure_field("ATC", (FocusInterval(0, 8),))
    assert timing.counted_seconds == 8
    assert timing.discarded_seconds == 0
    assert timing.was_capped is False


def test_several_visits_to_the_same_field_add_up() -> None:
    timing = measure_field("ATC", (FocusInterval(0, 5), FocusInterval(20, 27)))
    assert timing.counted_seconds == 12
    assert timing.interval_count == 2


def test_inactivity_above_the_threshold_is_discounted() -> None:
    """7.2: se descuenta la inactividad por encima de 60 segundos."""
    timing = measure_field("ADUDOMAXDIA", (FocusInterval(0, 3600),))
    assert timing.counted_seconds == INACTIVITY_THRESHOLD_SECONDS
    assert timing.discarded_seconds == 3600 - INACTIVITY_THRESHOLD_SECONDS
    assert timing.was_capped is True


def test_an_abandoned_screen_does_not_ruin_the_average() -> None:
    """Sin descuento, un campo de 8 segundos parecería de una hora."""
    honest = measure_field("A", (FocusInterval(0, 8),))
    abandoned = measure_field("B", (FocusInterval(0, 3600),))
    session = measure_session((("A", (FocusInterval(0, 8),)), ("B", (FocusInterval(0, 3600),))))
    assert honest.counted_seconds == 8
    assert abandoned.counted_seconds == 60
    assert session.seconds_per_field() == 34.0


def test_exactly_the_threshold_is_not_capped() -> None:
    timing = measure_field("ATC", (FocusInterval(0, INACTIVITY_THRESHOLD_SECONDS),))
    assert timing.counted_seconds == INACTIVITY_THRESHOLD_SECONDS
    assert timing.was_capped is False
    assert timing.discarded_seconds == 0


def test_discarded_time_is_reported_not_hidden() -> None:
    """Descartar en silencio impediría distinguir un campo difícil."""
    timing = measure_field("X", (FocusInterval(0, 200),))
    assert timing.total_observed_seconds == 200
    assert timing.counted_seconds == 60
    assert timing.discarded_seconds == 140


def test_field_without_intervals_counts_zero_and_is_still_measured() -> None:
    timing = measure_field("SIN_FOCO", ())
    assert timing.counted_seconds == 0
    assert timing.interval_count == 0


def test_intervals_are_ordered_before_measuring() -> None:
    unordered = measure_field("ATC", (FocusInterval(20, 27), FocusInterval(0, 5)))
    ordered = measure_field("ATC", (FocusInterval(0, 5), FocusInterval(20, 27)))
    assert unordered == ordered


def test_overlapping_intervals_are_an_error_not_a_guess() -> None:
    with pytest.raises(TimeMeasurementError, match="se solapan"):
        measure_field("ATC", (FocusInterval(0, 10), FocusInterval(5, 15)))


def test_interval_cannot_end_before_it_starts() -> None:
    with pytest.raises(ValueError):
        FocusInterval(10, 5)


def test_measurement_requires_a_field_name() -> None:
    with pytest.raises(ValueError):
        measure_field("", ())


def test_session_aggregates_counted_and_discarded_time() -> None:
    session = measure_session(
        (
            ("ATC", (FocusInterval(0, 10),)),
            ("FORMA", (FocusInterval(20, 32),)),
            ("ADUDOMAXDIA", (FocusInterval(40, 400),)),
        )
    )
    assert session.measured_field_count == 3
    assert session.counted_seconds == 10 + 12 + 60
    assert session.discarded_seconds == 300
    assert session.capped_field_count == 1


def test_session_without_fields_has_no_average() -> None:
    assert measure_session(()).seconds_per_field() is None


def test_a_field_cannot_be_measured_twice_in_one_session() -> None:
    with pytest.raises(TimeMeasurementError, match="dos veces"):
        measure_session((("ATC", (FocusInterval(0, 5),)), ("ATC", (FocusInterval(10, 15),))))


def test_measurement_is_deterministic() -> None:
    observations = (("B", (FocusInterval(0, 5),)), ("A", (FocusInterval(10, 20),)))
    assert measure_session(observations) == measure_session(observations)
