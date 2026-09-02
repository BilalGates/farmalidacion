"""Edición de bloques repetibles (DEV-507).

El plan de Fase 5 exige crear, eliminar, ordenar, fusionar y marcar no aplicable
las ocurrencias de un bloque repetible. Cada una de esas operaciones roza una
regla no negociable del proyecto: las ocurrencias se modelan explícitamente y
no se colapsan, y ningún valor de origen se pierde en silencio.

El módulo es puro: transforma una lista de ocurrencias en otra y describe qué
cambió. No persiste, no escribe auditoría y no renderiza. La auditoría de la
especificación 11 consumirá estas descripciones en lugar de reconstruirlas.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

BlockOperation = Literal[
    "crear",
    "eliminar",
    "reordenar",
    "fusionar",
    "marcar_no_aplicable",
    "revertir_no_aplicable",
]


class BlockEditingError(RuntimeError):
    """Operación que perdería datos o dejaría el bloque incoherente."""


@dataclass(frozen=True)
class BlockOccurrence:
    """Una ocurrencia explícita de un bloque repetible.

    `origin_provenance` distingue lo importado de lo añadido por un revisor.
    Una ocurrencia con procedencia de origen no puede eliminarse sin dejar
    rastro: representaría una fila de la fuente que dejó de existir.
    """

    occurrence_id: str
    ordinal: int
    values: tuple[tuple[str, str | None], ...]
    origin_provenance: str | None = None
    not_applicable: bool = False
    comment: str | None = None

    def __post_init__(self) -> None:
        if not self.occurrence_id:
            raise ValueError("La ocurrencia requiere identificador.")
        if self.ordinal < 1:
            raise ValueError("El ordinal de una ocurrencia empieza en 1.")
        names = [name for name, _ in self.values]
        if len(set(names)) != len(names):
            raise ValueError("Una ocurrencia no repite el mismo campo.")

    @property
    def is_from_source(self) -> bool:
        return self.origin_provenance is not None


@dataclass(frozen=True)
class BlockEdit:
    """Resultado de una operación, con lo necesario para auditarla."""

    operation: BlockOperation
    occurrences: tuple[BlockOccurrence, ...]
    affected_ids: tuple[str, ...]
    detail: str


def _renumber(occurrences: tuple[BlockOccurrence, ...]) -> tuple[BlockOccurrence, ...]:
    """Reasigna ordinales consecutivos conservando el orden dado."""
    return tuple(
        replace(item, ordinal=index)
        for index, item in enumerate(occurrences, start=1)
    )


def _require_unique(occurrences: tuple[BlockOccurrence, ...]) -> None:
    identifiers = [item.occurrence_id for item in occurrences]
    if len(set(identifiers)) != len(identifiers):
        raise BlockEditingError("Los identificadores de ocurrencia deben ser únicos.")


def create_occurrence(
    occurrences: tuple[BlockOccurrence, ...],
    new_occurrence: BlockOccurrence,
) -> BlockEdit:
    """Añade una ocurrencia al final del bloque."""
    _require_unique(occurrences)
    if any(item.occurrence_id == new_occurrence.occurrence_id for item in occurrences):
        raise BlockEditingError(
            f"La ocurrencia {new_occurrence.occurrence_id} ya existe en el bloque."
        )
    if new_occurrence.is_from_source:
        raise BlockEditingError(
            "Una ocurrencia creada por un revisor no puede declarar procedencia de origen."
        )
    result = _renumber((*occurrences, new_occurrence))
    return BlockEdit(
        "crear",
        result,
        (new_occurrence.occurrence_id,),
        "Ocurrencia añadida por decisión del revisor.",
    )


def delete_occurrence(
    occurrences: tuple[BlockOccurrence, ...],
    occurrence_id: str,
    comment: str | None = None,
) -> BlockEdit:
    """Elimina una ocurrencia.

    Una ocurrencia importada no se elimina sin comentario: representa una fila
    real de la fuente, y borrarla en silencio sería descartar un dato de origen.
    Marcarla `no_aplicable` suele ser la operación correcta.
    """
    _require_unique(occurrences)
    target = next(
        (item for item in occurrences if item.occurrence_id == occurrence_id), None
    )
    if target is None:
        raise BlockEditingError(f"La ocurrencia {occurrence_id} no existe en el bloque.")
    if target.is_from_source and not (comment or "").strip():
        raise BlockEditingError(
            "Eliminar una ocurrencia importada exige comentario del revisor; "
            "considere marcarla no aplicable en su lugar."
        )
    remaining = tuple(item for item in occurrences if item.occurrence_id != occurrence_id)
    return BlockEdit(
        "eliminar",
        _renumber(remaining),
        (occurrence_id,),
        (comment or "").strip() or "Ocurrencia añadida por el revisor y retirada.",
    )


def reorder_occurrences(
    occurrences: tuple[BlockOccurrence, ...],
    ordered_ids: tuple[str, ...],
) -> BlockEdit:
    """Reordena las ocurrencias según la secuencia dada.

    La secuencia debe cubrir exactamente las ocurrencias existentes: omitir una
    la eliminaría de hecho, y reordenar no es una vía para borrar.
    """
    _require_unique(occurrences)
    existing = {item.occurrence_id: item for item in occurrences}
    if len(set(ordered_ids)) != len(ordered_ids):
        raise BlockEditingError("El orden solicitado repite una ocurrencia.")
    if set(ordered_ids) != set(existing):
        raise BlockEditingError(
            "El orden solicitado debe incluir todas las ocurrencias y ninguna más."
        )
    result = _renumber(tuple(existing[identifier] for identifier in ordered_ids))
    return BlockEdit("reordenar", result, ordered_ids, "Ocurrencias reordenadas.")


def merge_occurrences(
    occurrences: tuple[BlockOccurrence, ...],
    source_id: str,
    target_id: str,
    comment: str,
) -> BlockEdit:
    """Fusiona dos ocurrencias en una.

    Fusionar es la operación más peligrosa del bloque: colapsa dos filas en una
    y contradice la regla de modelar ocurrencias explícitamente. Por eso exige
    comentario y **falla si las dos aportan valores distintos para el mismo
    campo**: elegir uno de los dos sería decidir un dato clínico por el revisor
    sin que quede constancia de qué se descartó.
    """
    _require_unique(occurrences)
    if source_id == target_id:
        raise BlockEditingError("No se fusiona una ocurrencia consigo misma.")
    if not comment.strip():
        raise BlockEditingError("Fusionar ocurrencias exige comentario del revisor.")

    existing = {item.occurrence_id: item for item in occurrences}
    for identifier in (source_id, target_id):
        if identifier not in existing:
            raise BlockEditingError(f"La ocurrencia {identifier} no existe en el bloque.")

    source, target = existing[source_id], existing[target_id]
    source_values = dict(source.values)
    merged = dict(target.values)
    for name, value in source_values.items():
        # Solo hay conflicto cuando ambas ocurrencias afirman algo y difieren.
        # Un ausente frente a un valor es complementario, no contradictorio.
        if (
            value is not None
            and merged.get(name) is not None
            and merged[name] != value
        ):
            raise BlockEditingError(
                f"Las ocurrencias declaran valores distintos para {name}; "
                "resuelva el conflicto antes de fusionar."
            )
        if merged.get(name) is None and value is not None:
            merged[name] = value
        merged.setdefault(name, None)

    fused = replace(target, values=tuple(sorted(merged.items())), comment=comment.strip())
    remaining = tuple(
        fused if item.occurrence_id == target_id else item
        for item in occurrences
        if item.occurrence_id != source_id
    )
    return BlockEdit(
        "fusionar",
        _renumber(remaining),
        (source_id, target_id),
        comment.strip(),
    )


def mark_not_applicable(
    occurrences: tuple[BlockOccurrence, ...],
    occurrence_id: str,
    comment: str,
) -> BlockEdit:
    """Marca una ocurrencia como no aplicable sin alterar sus valores.

    DEV-011: un bloque puede marcarse `not_applicable` lógicamente sin alterar
    ocurrencias; es reversible y auditado. Los valores se conservan intactos.
    """
    _require_unique(occurrences)
    if not comment.strip():
        raise BlockEditingError("Marcar no aplicable exige comentario del revisor.")
    if not any(item.occurrence_id == occurrence_id for item in occurrences):
        raise BlockEditingError(f"La ocurrencia {occurrence_id} no existe en el bloque.")

    result = tuple(
        replace(item, not_applicable=True, comment=comment.strip())
        if item.occurrence_id == occurrence_id
        else item
        for item in occurrences
    )
    return BlockEdit("marcar_no_aplicable", result, (occurrence_id,), comment.strip())


def revert_not_applicable(
    occurrences: tuple[BlockOccurrence, ...],
    occurrence_id: str,
    comment: str,
) -> BlockEdit:
    """Revierte la marca de no aplicable. DEV-011 la declara reversible."""
    _require_unique(occurrences)
    if not comment.strip():
        raise BlockEditingError("Revertir no aplicable exige comentario del revisor.")
    target = next(
        (item for item in occurrences if item.occurrence_id == occurrence_id), None
    )
    if target is None:
        raise BlockEditingError(f"La ocurrencia {occurrence_id} no existe en el bloque.")
    if not target.not_applicable:
        raise BlockEditingError(
            f"La ocurrencia {occurrence_id} no está marcada como no aplicable."
        )

    result = tuple(
        replace(item, not_applicable=False, comment=comment.strip())
        if item.occurrence_id == occurrence_id
        else item
        for item in occurrences
    )
    return BlockEdit("revertir_no_aplicable", result, (occurrence_id,), comment.strip())
