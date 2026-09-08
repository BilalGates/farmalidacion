"""Reglas de riesgo por prefijo ATC (DEV-606).

La especificación 11.1 fija el **mecanismo**: coincidencia por prefijo sobre el
código ATC, y si un registro casa con cualquier regla activa exige doble
validación. Ese mecanismo es determinista y no requiere criterio clínico, así
que se implementa entero.

Lo que **no** decide este módulo es qué prefijos son de riesgo. La única semilla
acordada es `L04` (inmunosupresores), y así consta en la especificación. Ampliar
la lista es D-017, marcada en el registro de decisiones como *decisión exclusiva
de farmacia*: la especificación menciona antineoplásicos, antitrombóticos,
insulinas, opioides y electrolitos concentrados como candidatos «a decidir por
farmacia y no por el desarrollo». Añadirlos aquí sería exactamente eso.

Por eso las reglas son un dato configurable y no una constante del módulo, y por
eso el mantenimiento no exige desplegar código.

Comportamiento conservador ante la ausencia de ATC: un registro **sin** código
ATC no se declara de bajo riesgo. No se sabe, y no saberlo no es lo mismo que
saber que no. `requires_double_review` devuelve `None` en ese caso para que
quien llame decida, en lugar de recibir un `False` que parece una respuesta.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: Un código ATC bien formado: letra, dos dígitos, letra, letra, dos dígitos,
#: truncable en cualquier nivel (`L`, `L04`, `L04A`, `L04AB`, `L04AB01`).
ATC_PATTERN = re.compile(r"^[A-Z](?:\d{2}(?:[A-Z](?:[A-Z](?:\d{2})?)?)?)?$")


class RiskRuleError(ValueError):
    """Regla de riesgo mal formada."""


@dataclass(frozen=True)
class RiskRule:
    """Regla de riesgo por prefijo ATC.

    `reason` se muestra al revisor: una regla que exige doble validación sin
    decir por qué convierte una salvaguarda clínica en un obstáculo opaco.
    """

    atc_prefix: str
    reason: str
    active: bool = True

    def __post_init__(self) -> None:
        if not self.atc_prefix:
            raise RiskRuleError("Una regla de riesgo exige prefijo ATC.")
        normalized = self.atc_prefix.strip().upper()
        if not ATC_PATTERN.match(normalized):
            raise RiskRuleError(
                f"{self.atc_prefix!r} no es un prefijo ATC válido. "
                "Un prefijo mal formado no casaría con nada y desactivaría la "
                "regla en silencio."
            )
        if not (self.reason or "").strip():
            raise RiskRuleError(
                "Una regla de riesgo exige motivo: se muestra al revisor."
            )
        object.__setattr__(self, "atc_prefix", normalized)

    def matches(self, atc_code: str) -> bool:
        """Coincidencia por prefijo, según la especificación 11.1."""
        return atc_code.strip().upper().startswith(self.atc_prefix)


#: Semilla acordada en la especificación 11.1. **No se amplía desde el código.**
#:
#: D-017 (ampliar la lista) es decisión exclusiva de farmacia. Añadir aquí un
#: prefijo sería decidir qué medicamentos son de alto riesgo, que es justo lo
#: que el desarrollo no puede hacer.
SEED_RULES: tuple[RiskRule, ...] = (
    RiskRule(
        atc_prefix="L04",
        reason="Inmunosupresores: semilla acordada en la especificación 11.1.",
    ),
)


@dataclass(frozen=True)
class RiskAssessment:
    """Resultado de evaluar un registro contra las reglas activas."""

    #: `None` cuando no hay ATC: no se sabe, y eso no es «no es de riesgo».
    requires_double_review: bool | None
    matched: tuple[RiskRule, ...]
    reason: str

    @property
    def is_undetermined(self) -> bool:
        return self.requires_double_review is None


def assess(
    atc_code: str | None, rules: tuple[RiskRule, ...] = SEED_RULES
) -> RiskAssessment:
    """Evalúa si un registro exige doble validación.

    Sin código ATC el resultado es indeterminado, no negativo. Un registro cuyo
    riesgo no se ha podido clasificar no debe pasar como clasificado de bajo
    riesgo: quien llame decide si eso bloquea la entrega o exige revisión.
    """
    if atc_code is None or not atc_code.strip():
        return RiskAssessment(
            requires_double_review=None,
            matched=(),
            reason=(
                "El registro no declara código ATC: su riesgo no se ha podido "
                "clasificar. No consta que sea de bajo riesgo."
            ),
        )

    code = atc_code.strip().upper()
    if not ATC_PATTERN.match(code):
        return RiskAssessment(
            requires_double_review=None,
            matched=(),
            reason=(
                f"El código ATC {atc_code!r} no está bien formado; la "
                "clasificación de riesgo queda indeterminada."
            ),
        )

    matched = tuple(rule for rule in rules if rule.active and rule.matches(code))
    if matched:
        motives = "; ".join(rule.reason for rule in matched)
        return RiskAssessment(
            requires_double_review=True,
            matched=matched,
            reason=f"El ATC {code} casa con {len(matched)} regla(s): {motives}",
        )
    return RiskAssessment(
        requires_double_review=False,
        matched=(),
        reason=f"El ATC {code} no casa con ninguna regla de riesgo activa.",
    )


def validate_rules(rules: tuple[RiskRule, ...]) -> None:
    """Comprueba un conjunto de reglas antes de aplicarlo.

    Dos reglas con el mismo prefijo no son un error grave, pero sí una señal de
    que la lista se mantuvo a mano sin revisarla; se rechaza para que el
    mantenimiento desde la interfaz no acumule duplicados invisibles.
    """
    prefixes = [rule.atc_prefix for rule in rules]
    duplicated = {item for item in prefixes if prefixes.count(item) > 1}
    if duplicated:
        raise RiskRuleError(
            f"Prefijos ATC repetidos en las reglas: {sorted(duplicated)}."
        )
