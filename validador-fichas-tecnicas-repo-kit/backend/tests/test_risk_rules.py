"""Reglas de riesgo por prefijo ATC (DEV-606).

El mecanismo de la especificación 11.1 es determinista y se comprueba entero.
Lo que estas pruebas también fijan es lo que el módulo **no** debe hacer:
ampliar por su cuenta la lista de prefijos de riesgo, que es D-017 y decisión
exclusiva de farmacia.
"""

from __future__ import annotations

import pytest

from pharma_validator_api.risk_rules import (
    SEED_RULES,
    RiskRule,
    RiskRuleError,
    assess,
    validate_rules,
)


def test_prefix_matching_follows_the_specification() -> None:
    # 11.1: un registro con ATC `L04AB01` casa con la regla `L04`.
    result = assess("L04AB01")
    assert result.requires_double_review is True
    assert result.matched[0].atc_prefix == "L04"
    # El motivo llega para poder mostrarlo al revisor.
    assert "Inmunosupresores" in result.reason


def test_a_code_outside_the_rules_does_not_require_double_review() -> None:
    result = assess("A02BC01")
    assert result.requires_double_review is False
    assert result.matched == ()


def test_matching_is_case_and_whitespace_insensitive() -> None:
    assert assess("  l04ab01 ").requires_double_review is True


def test_a_partial_code_matches_only_at_prefix_level() -> None:
    # `L04` casa consigo mismo; `L0` no es un código ATC completo pero tampoco
    # debe casar con la regla `L04`.
    assert assess("L04").requires_double_review is True
    assert assess("L01AA01").requires_double_review is False


def test_a_record_without_atc_is_not_declared_low_risk() -> None:
    # Lo importante: no se sabe, y no saberlo no es saber que no.
    for value in (None, "", "   "):
        result = assess(value)
        assert result.requires_double_review is None
        assert result.is_undetermined
        assert "No consta que sea de bajo riesgo" in result.reason


def test_a_malformed_code_leaves_the_risk_undetermined() -> None:
    for value in ("no-es-atc", "1234", "L4"):
        result = assess(value)
        assert result.requires_double_review is None
        assert "indeterminada" in result.reason


def test_an_inactive_rule_does_not_match() -> None:
    rules = (RiskRule("L04", "Inmunosupresores.", active=False),)
    assert assess("L04AB01", rules).requires_double_review is False


def test_several_matching_rules_are_all_reported() -> None:
    rules = (
        RiskRule("L", "Antineoplásicos e inmunomoduladores."),
        RiskRule("L04", "Inmunosupresores."),
    )
    result = assess("L04AB01", rules)
    assert result.requires_double_review is True
    assert len(result.matched) == 2


def test_a_malformed_prefix_is_refused_instead_of_silently_never_matching() -> None:
    # Una regla con prefijo inválido no casaría con nada y quedaría desactivada
    # sin que nadie lo notase: es peor que un error.
    with pytest.raises(RiskRuleError, match="no es un prefijo ATC válido"):
        RiskRule("no-es-atc", "Motivo.")


def test_a_rule_requires_a_reason_shown_to_the_reviewer() -> None:
    with pytest.raises(RiskRuleError, match="exige motivo"):
        RiskRule("L04", "   ")


def test_duplicated_prefixes_are_refused() -> None:
    with pytest.raises(RiskRuleError, match="repetidos"):
        validate_rules((RiskRule("L04", "Uno."), RiskRule("L04", "Otro.")))


def test_the_seed_contains_only_what_the_specification_agreed() -> None:
    # D-017 es decisión exclusiva de farmacia. Si esta prueba falla porque
    # alguien añadió un prefijo, la pregunta no es cuál añadió: es quién lo
    # decidió. La especificación 11.1 sólo acordó `L04`.
    assert [rule.atc_prefix for rule in SEED_RULES] == ["L04"]
    validate_rules(SEED_RULES)


def test_the_rules_are_configurable_without_touching_code() -> None:
    # 11.1 exige que el mantenimiento sea accesible sin desplegar código: las
    # reglas entran como dato.
    extended = (*SEED_RULES, RiskRule("B01AB", "Regla de prueba, no clínica."))
    validate_rules(extended)
    assert assess("B01AB05", extended).requires_double_review is True
    # Y sin ellas, el mismo código no exige doble validación.
    assert assess("B01AB05").requires_double_review is False
