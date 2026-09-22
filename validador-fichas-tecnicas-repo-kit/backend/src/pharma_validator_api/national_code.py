"""Representación conservadora del Código Nacional de una presentación.

El producto trabaja habitualmente con seis dígitos, pero algunas fuentes e
integraciones transportan un séptimo dígito de control. Este módulo separa ambas
representaciones sin afirmar todavía una regla de cálculo no aprobada.

No es una función de enlace ni de identidad. Extraer los seis primeros dígitos
de una entrada de siete permite buscar, pero no autoriza a fusionar registros ni
a sustituir el literal conservado de la fuente.
"""

from dataclasses import dataclass
from typing import Literal

CheckDigitStatus = Literal["not_supplied", "not_validated"]


class NationalCodeError(ValueError):
    """La entrada no puede representarse como CN de seis o siete dígitos."""


@dataclass(frozen=True)
class NationalCode:
    """CN de trabajo y representación recibida, mantenidas por separado."""

    canonical_six: str
    source_literal: str
    check_digit: str | None
    check_digit_status: CheckDigitStatus


def parse_national_code(value: str) -> NationalCode:
    """Analiza una entrada de usuario sin validar ni descartar su control.

    Sólo se retira espacio exterior propio de un formulario. Separadores,
    letras y cualquier otra transformación quedan prohibidos: aceptarlos aquí
    convertiría una comodidad de búsqueda en una normalización de identidad.
    """

    literal = value.strip()
    if len(literal) not in (6, 7) or not literal.isascii() or not literal.isdigit():
        raise NationalCodeError("El Código Nacional debe contener seis o siete dígitos.")

    check_digit = literal[6] if len(literal) == 7 else None
    return NationalCode(
        canonical_six=literal[:6],
        source_literal=literal,
        check_digit=check_digit,
        check_digit_status="not_validated" if check_digit is not None else "not_supplied",
    )


def national_code_search_term(value: str) -> str:
    """Devuelve el término canónico de búsqueda, nunca una identidad nueva."""

    return parse_national_code(value).canonical_six

