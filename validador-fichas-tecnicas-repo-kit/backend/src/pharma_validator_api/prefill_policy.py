"""Reglas de pre-relleno y defensa frente al sesgo de automatización (DEV-510).

La especificación 9 es la razón de ser del diseño: un farmacéutico que revisa
300 registros en una mañana acepta lo que la pantalla le propone. Si la
herramienta rellena un campo que requiere criterio clínico, el resultado es un
dato que nadie decidió realmente, con la apariencia de haber sido validado.

Este módulo decide qué puede mostrarse ya escrito y qué debe quedar vacío. Es
puro y no depende de la interfaz: la pantalla consume estas decisiones en lugar
de reimplementarlas, de modo que la regla se pueda probar sin renderizar nada.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pharma_validator_api.evidence_verification import PrefillPolicy

FieldPresentation = Literal[
    "valor_precargado",
    "opciones_sin_marcar",
    "casilla_vacia",
    "no_visible",
]


class PrefillPolicyError(RuntimeError):
    """Intento de presentar un campo violando la especificación 9."""


@dataclass(frozen=True)
class EvidenceCitation:
    """Cita ya verificada por DEV-405, lista para mostrarse en contexto."""

    section: str
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class FieldPresentationPlan:
    """Cómo debe presentarse un campo en la pantalla de revisión."""

    field_name: str
    policy: PrefillPolicy
    presentation: FieldPresentation
    prefilled_value: str | None
    options: tuple[str, ...]
    evidence: EvidenceCitation | None
    warning: str | None = None

    @property
    def is_protected(self) -> bool:
        """Un campo protegido nunca llega con una decisión tomada."""
        return self.policy in ("proponer_opciones", "solo_evidencia")

    @property
    def can_be_bulk_confirmed(self) -> bool:
        """9.3: solo `proponer_valor` con evidencia visible admite bloque."""
        return self.policy == "proponer_valor" and self.evidence is not None


CLINICAL_JUDGEMENT_WARNING = (
    "La ficha técnica no declara este dato. Este valor es criterio farmacéutico."
)


def plan_field_presentation(
    field_name: str,
    policy: PrefillPolicy,
    proposed_value: str | None = None,
    options: tuple[str, ...] = (),
    evidence: EvidenceCitation | None = None,
) -> FieldPresentationPlan:
    """Decide la presentación de un campo según su política.

    La función no confía en que quien llama respete la política: si se le pasa
    un valor para un campo protegido, lo descarta en lugar de mostrarlo. Es la
    diferencia entre una regla y una recomendación.
    """
    if policy == "oculto":
        # 9.2: el campo no aparece en esta pantalla; se puebla desde otra fuente.
        return FieldPresentationPlan(
            field_name, policy, "no_visible", None, (), None
        )

    if policy == "proponer_valor":
        return FieldPresentationPlan(
            field_name,
            policy,
            "valor_precargado",
            proposed_value,
            (),
            evidence,
        )

    if policy == "proponer_opciones":
        # 9.2: candidatos normalizados, con ninguno preseleccionado.
        return FieldPresentationPlan(
            field_name,
            policy,
            "opciones_sin_marcar",
            None,
            tuple(options),
            evidence,
        )

    # solo_evidencia: la casilla queda vacía. Ningún número sugerido, ninguna
    # casilla marcada por defecto. El número lo escribe una persona.
    return FieldPresentationPlan(
        field_name,
        policy,
        "casilla_vacia",
        None,
        (),
        evidence,
        CLINICAL_JUDGEMENT_WARNING,
    )


def assert_no_protected_preselection(plans: tuple[FieldPresentationPlan, ...]) -> None:
    """Comprobación de seguridad ejecutable sobre una pantalla completa.

    Sirve como prueba automática de las políticas de pre-relleno que exige la
    puerta de salida de Fase 5: ningún campo protegido aparece con valor.
    """
    for plan in plans:
        if not plan.is_protected:
            continue
        if plan.prefilled_value is not None:
            raise PrefillPolicyError(
                f"El campo protegido {plan.field_name} llega con un valor precargado."
            )
        if plan.presentation == "valor_precargado":
            raise PrefillPolicyError(
                f"El campo protegido {plan.field_name} no puede precargar valor."
            )


def select_bulk_confirmable(
    plans: tuple[FieldPresentationPlan, ...],
) -> tuple[FieldPresentationPlan, ...]:
    """Filtra los campos que admiten confirmación en bloque.

    9.3 lo permite solo para `proponer_valor` y solo si su evidencia está
    visible. Nunca para `proponer_opciones` ni `solo_evidencia`, ni desde una
    vista donde la evidencia no se esté mostrando.
    """
    return tuple(plan for plan in plans if plan.can_be_bulk_confirmed)


def assert_bulk_confirmation_allowed(
    plans: tuple[FieldPresentationPlan, ...], evidence_visible: bool
) -> None:
    """Valida una confirmación en bloque antes de aplicarla."""
    if not evidence_visible:
        raise PrefillPolicyError(
            "No se permite confirmación en bloque sin la evidencia visible en pantalla."
        )
    for plan in plans:
        if not plan.can_be_bulk_confirmed:
            raise PrefillPolicyError(
                f"El campo {plan.field_name} con política {plan.policy} "
                "no admite confirmación en bloque."
            )
