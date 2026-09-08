"""La distinción implementada / validada no puede diluirse en silencio."""

import pytest

from pharma_validator_api.config import Settings
from pharma_validator_api.maturity import (
    CAPABILITIES,
    Capability,
    MaturityError,
    assert_no_capability_claims_clinical_validation,
    clinical_blockers,
    rank,
)


def test_no_capability_is_declared_clinically_validated() -> None:
    """Mientras no exista oro anotado, nada del sistema está validado."""
    assert_no_capability_claims_clinical_validation()
    assert not any(c.is_clinically_validated for c in CAPABILITIES)


def test_a_capability_cannot_claim_validation_with_open_blockers() -> None:
    with pytest.raises(MaturityError):
        Capability("x", "clinicamente_validada", clinical_blockers=("GOLD-002",))


def test_production_ready_also_requires_no_open_blockers() -> None:
    with pytest.raises(MaturityError):
        Capability("x", "lista_para_produccion", clinical_blockers=("D-015",))


def test_the_known_clinical_blockers_are_reported() -> None:
    assert set(clinical_blockers()) >= {"D-014", "D-015", "GOLD-002"}


def test_levels_are_ordered() -> None:
    assert rank("implementada") < rank("tecnicamente_verificada")
    assert rank("tecnicamente_verificada") < rank("clinicamente_validada")


def test_settings_cannot_declare_clinical_validation() -> None:
    """Encender una bandera no convierte el sistema en clínicamente validado."""
    settings = Settings(enable_llm_prefill=True, enable_export=True)
    assert settings.clinically_validated is False


def test_clinical_features_are_off_by_default() -> None:
    """Defaults conservadores: nada clínico se enciende por haberse programado."""
    settings = Settings()
    assert settings.enable_llm_prefill is False
    assert settings.enable_second_review is False
    assert settings.enable_export is False
    assert settings.enable_cima_link is False
    assert settings.enable_auto_revalidation is False
