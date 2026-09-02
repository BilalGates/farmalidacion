"""Identificación declarada del revisor (DEV-501).

La especificación 10.1 es explícita: no hay LDAP ni contraseñas. Al abrir la
aplicación se elige el nombre propio de una lista configurable. Es un selector,
no un inicio de sesión.

La consecuencia que la especificación pide tener presente: sin autenticación, la
firma de cada validación es **declarada, no demostrada**. Identifica quién dijo
ser, no quién era. Para utillaje interno en un equipo pequeño es razonable, pero
no sostendría una auditoría formal. Este módulo lo hace explícito en el tipo, en
lugar de dejarlo en un comentario que se pierde.

La aplicación debe rechazar guardar validaciones sin usuario seleccionado, y esa
regla se implementa aquí para que no dependa de que cada endpoint la recuerde.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AssuranceLevel = Literal["declarada"]


class ReviewerIdentityError(RuntimeError):
    """Intento de operar sin un revisor válido de la lista configurada."""


@dataclass(frozen=True)
class Reviewer:
    """Revisor elegido de la lista configurable.

    `assurance` es siempre `declarada` en el piloto. El campo existe para que
    una futura autenticación real (D-018, reevaluable en Fase 8) sea un cambio
    de valor y no una reinterpretación silenciosa de lo que significa la firma.
    """

    identifier: str
    display_name: str
    assurance: AssuranceLevel = "declarada"

    def __post_init__(self) -> None:
        if not self.identifier.strip():
            raise ValueError("El revisor requiere identificador.")
        if not self.display_name.strip():
            raise ValueError("El revisor requiere nombre visible.")


@dataclass(frozen=True)
class ReviewerDirectory:
    """Lista configurable de revisores.

    No se crean revisores sobre la marcha: un nombre que no está en la
    configuración no puede firmar una validación, porque entonces la lista
    dejaría de ser el registro de quién puede revisar.
    """

    reviewers: tuple[Reviewer, ...]

    def __post_init__(self) -> None:
        identifiers = [item.identifier for item in self.reviewers]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Los identificadores de revisor deben ser únicos.")

    @classmethod
    def from_configuration(cls, entries: tuple[str, ...]) -> ReviewerDirectory:
        """Construye la lista desde configuración, con formato `id:Nombre`."""
        reviewers = []
        for entry in entries:
            identifier, separator, display_name = entry.partition(":")
            if not separator:
                raise ValueError(
                    f"La entrada {entry!r} debe tener el formato 'identificador:Nombre'."
                )
            reviewers.append(Reviewer(identifier.strip(), display_name.strip()))
        return cls(tuple(reviewers))

    def resolve(self, identifier: str | None) -> Reviewer:
        """Devuelve el revisor elegido o falla de forma explícita.

        Un identificador ausente y uno desconocido son errores distintos: el
        primero indica que la pantalla no pidió usuario, el segundo que se
        intentó firmar con un nombre fuera de la lista.
        """
        if identifier is None or not identifier.strip():
            raise ReviewerIdentityError(
                "No se puede guardar una validación sin revisor seleccionado."
            )
        for reviewer in self.reviewers:
            if reviewer.identifier == identifier:
                return reviewer
        raise ReviewerIdentityError(
            f"El revisor {identifier!r} no pertenece a la lista configurada."
        )

    def require_distinct(self, first: str | None, second: str | None) -> tuple[Reviewer, Reviewer]:
        """Exige dos revisores distintos para la doble validación.

        11.1: los registros de alto riesgo requieren validación independiente
        por dos usuarios distintos. Comprobarlo aquí evita que una segunda
        validación la firme quien ya hizo la primera.
        """
        one, two = self.resolve(first), self.resolve(second)
        if one.identifier == two.identifier:
            raise ReviewerIdentityError(
                "La doble validación exige dos revisores distintos."
            )
        return one, two
