import pytest

from pharma_validator_api.evidence_verification import DocumentSection
from pharma_validator_api.extraction_batches import (
    CompletedUnit,
    ExtractionBatchError,
    ExtractionConfiguration,
    WorkUnit,
    plan_batch,
)
from pharma_validator_api.extractor import ExtractorIdentity, FieldRequest, SectionRequest

IDENTITY = ExtractorIdentity("extractor-v1", "modelo-7b")


def configuration(**overrides: str) -> ExtractionConfiguration:
    values = {"prompt_version": "prompt-v1", "schema_version": "guided-extraction-v1"}
    values.update(overrides)
    identity = ExtractorIdentity(
        overrides.get("extractor_version", "extractor-v1"),
        overrides.get("model", "modelo-7b"),
    )
    return ExtractionConfiguration(
        identity, values["prompt_version"], values["schema_version"]
    )


def request(section: str = "4.2", *fields: str) -> SectionRequest:
    names = fields or ("POSOLOGIA",)
    return SectionRequest(
        "version-1",
        "Omeprazol 20 mg",
        DocumentSection("version-1", section, f"<p>{section}</p>"),
        tuple(
            FieldRequest(name, "d", "CHAR(100)", "proponer_valor") for name in names
        ),
    )


def key_of(item: SectionRequest) -> str:
    return WorkUnit(
        item.document_version_id,
        item.section.section,
        tuple(field.field_name for field in item.fields),
    ).key


def test_everything_is_pending_without_previous_state() -> None:
    plan = plan_batch((request("4.2"), request("5.1")), configuration())
    assert len(plan.pending) == 2
    assert plan.reused == ()
    assert plan.total_units == 2


def test_completed_unit_with_the_same_configuration_is_reused() -> None:
    first = request("4.2")
    config = configuration()
    done = CompletedUnit(key_of(first), config.fingerprint(), "completada")
    plan = plan_batch((first, request("5.1")), config, (done,))
    assert [item.section.section for item in plan.pending] == ["5.1"]
    assert plan.reused == (key_of(first),)


def test_changing_the_model_supersedes_previous_work_without_deleting_it() -> None:
    first = request("4.2")
    done = CompletedUnit(key_of(first), configuration().fingerprint(), "completada")
    plan = plan_batch((first,), configuration(model="modelo-30b"), (done,))
    assert len(plan.pending) == 1
    assert plan.superseded == (key_of(first),)
    assert plan.reused == ()


def test_changing_the_prompt_version_supersedes_previous_work() -> None:
    first = request("4.2")
    done = CompletedUnit(key_of(first), configuration().fingerprint(), "completada")
    plan = plan_batch((first,), configuration(prompt_version="prompt-v2"), (done,))
    assert plan.superseded == (key_of(first),)


def test_changing_the_schema_version_supersedes_previous_work() -> None:
    first = request("4.2")
    done = CompletedUnit(key_of(first), configuration().fingerprint(), "completada")
    plan = plan_batch((first,), configuration(schema_version="guided-v2"), (done,))
    assert plan.superseded == (key_of(first),)


def test_incidents_are_retried_by_default() -> None:
    first = request("4.2")
    config = configuration()
    done = CompletedUnit(key_of(first), config.fingerprint(), "incidencia")
    plan = plan_batch((first,), config, (done,))
    assert len(plan.pending) == 1
    assert plan.retried == (key_of(first),)


def test_incidents_can_be_left_alone_when_retry_is_disabled() -> None:
    first = request("4.2")
    config = configuration()
    done = CompletedUnit(key_of(first), config.fingerprint(), "incidencia")
    plan = plan_batch((first,), config, (done,), retry_incidents=False)
    assert plan.pending == ()
    assert plan.reused == (key_of(first),)


def test_state_from_another_batch_is_ignored_and_not_touched() -> None:
    plan = plan_batch(
        (request("4.2"),),
        configuration(),
        (CompletedUnit("clave-de-otro-lote", configuration().fingerprint(), "completada"),),
    )
    assert len(plan.pending) == 1
    assert plan.reused == ()
    assert plan.superseded == ()


def test_unit_key_depends_on_the_requested_fields() -> None:
    one = key_of(request("4.2", "POSOLOGIA"))
    two = key_of(request("4.2", "POSOLOGIA", "VIA"))
    assert one != two


def test_unit_key_ignores_field_order() -> None:
    one = WorkUnit("version-1", "4.2", ("VIA", "POSOLOGIA")).key
    two = WorkUnit("version-1", "4.2", ("POSOLOGIA", "VIA")).key
    assert one == two


def test_fingerprint_is_stable_and_configuration_sensitive() -> None:
    assert configuration().fingerprint() == configuration().fingerprint()
    assert configuration().fingerprint() != configuration(model="otro").fingerprint()


def test_configuration_requires_prompt_and_schema_versions() -> None:
    with pytest.raises(ValueError):
        ExtractionConfiguration(IDENTITY, "", "guided-extraction-v1")


def test_completed_unit_cannot_be_pending() -> None:
    with pytest.raises(ValueError):
        CompletedUnit("clave", "huella", "pendiente")


def test_duplicate_work_units_are_a_usage_error() -> None:
    with pytest.raises(ExtractionBatchError, match="agrupación"):
        plan_batch((request("4.2"), request("4.2")), configuration())


def test_repeated_state_entry_is_a_usage_error() -> None:
    first = request("4.2")
    config = configuration()
    done = CompletedUnit(key_of(first), config.fingerprint(), "completada")
    with pytest.raises(ExtractionBatchError, match="repetida"):
        plan_batch((first,), config, (done, done))


def test_plan_is_deterministic() -> None:
    requests = (request("5.1"), request("4.2"))
    first = plan_batch(requests, configuration())
    second = plan_batch(requests, configuration())
    assert first == second


def test_resuming_an_interrupted_batch_only_runs_what_is_missing() -> None:
    requests = tuple(request(section) for section in ("1", "2", "4.2", "5.1", "6.6"))
    config = configuration()
    done = tuple(
        CompletedUnit(key_of(item), config.fingerprint(), "completada")
        for item in requests[:3]
    )
    plan = plan_batch(requests, config, done)
    assert [item.section.section for item in plan.pending] == ["5.1", "6.6"]
    assert len(plan.reused) == 3
    assert plan.total_units == 5
