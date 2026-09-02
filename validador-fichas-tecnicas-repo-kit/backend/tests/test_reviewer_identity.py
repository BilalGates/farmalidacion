import pytest

from pharma_validator_api.reviewer_identity import (
    Reviewer,
    ReviewerDirectory,
    ReviewerIdentityError,
)

DIRECTORY = ReviewerDirectory.from_configuration(
    ("mtorres:M. Torres", "jlopez:J. López")
)


def test_directory_is_built_from_configuration() -> None:
    assert [item.identifier for item in DIRECTORY.reviewers] == ["mtorres", "jlopez"]
    assert DIRECTORY.reviewers[0].display_name == "M. Torres"


def test_configuration_entry_requires_identifier_and_name() -> None:
    with pytest.raises(ValueError, match="identificador:Nombre"):
        ReviewerDirectory.from_configuration(("solo-nombre",))


def test_duplicate_identifiers_are_rejected() -> None:
    with pytest.raises(ValueError, match="únicos"):
        ReviewerDirectory.from_configuration(("a:Ana", "a:Otra Ana"))


def test_reviewer_requires_identifier_and_display_name() -> None:
    with pytest.raises(ValueError):
        Reviewer("", "Nombre")
    with pytest.raises(ValueError):
        Reviewer("id", "   ")


def test_selected_reviewer_is_resolved() -> None:
    reviewer = DIRECTORY.resolve("mtorres")
    assert reviewer.display_name == "M. Torres"


def test_saving_without_a_selected_reviewer_is_refused() -> None:
    """10.1: la aplicación rechaza guardar validaciones sin usuario."""
    for missing in (None, "", "   "):
        with pytest.raises(ReviewerIdentityError, match="sin revisor seleccionado"):
            DIRECTORY.resolve(missing)


def test_reviewer_outside_the_configured_list_cannot_sign() -> None:
    with pytest.raises(ReviewerIdentityError, match="no pertenece"):
        DIRECTORY.resolve("intruso")


def test_missing_and_unknown_reviewer_are_different_errors() -> None:
    with pytest.raises(ReviewerIdentityError) as missing:
        DIRECTORY.resolve(None)
    with pytest.raises(ReviewerIdentityError) as unknown:
        DIRECTORY.resolve("intruso")
    assert str(missing.value) != str(unknown.value)


def test_assurance_is_declared_not_demonstrated() -> None:
    """La firma identifica quién dijo ser, no quién era."""
    assert DIRECTORY.resolve("mtorres").assurance == "declarada"


def test_double_validation_requires_two_distinct_reviewers() -> None:
    first, second = DIRECTORY.require_distinct("mtorres", "jlopez")
    assert first.identifier != second.identifier


def test_double_validation_refuses_the_same_reviewer_twice() -> None:
    with pytest.raises(ReviewerIdentityError, match="dos revisores distintos"):
        DIRECTORY.require_distinct("mtorres", "mtorres")


def test_double_validation_refuses_an_unselected_second_reviewer() -> None:
    with pytest.raises(ReviewerIdentityError, match="sin revisor seleccionado"):
        DIRECTORY.require_distinct("mtorres", None)


def test_empty_directory_cannot_sign_anything() -> None:
    empty = ReviewerDirectory(())
    with pytest.raises(ReviewerIdentityError):
        empty.resolve("mtorres")


def test_directory_is_built_from_application_settings(monkeypatch) -> None:
    """El formato documentado en .env.example se lee sin adaptaciones."""
    from pharma_validator_api.config import Settings

    monkeypatch.setenv("APP_REVIEWERS", '["mtorres:M. Torres","jlopez:J. Lopez"]')
    settings = Settings(_env_file=None)
    directory = ReviewerDirectory.from_configuration(settings.reviewers)
    assert directory.resolve("mtorres").display_name == "M. Torres"


def test_unconfigured_reviewers_cannot_sign(monkeypatch) -> None:
    from pharma_validator_api.config import Settings

    monkeypatch.delenv("APP_REVIEWERS", raising=False)
    settings = Settings(_env_file=None)
    directory = ReviewerDirectory.from_configuration(settings.reviewers)
    with pytest.raises(ReviewerIdentityError):
        directory.resolve("mtorres")
