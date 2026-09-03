"""Selección reproducible del conjunto oro (DEV-407, parte de selección).

Este módulo implementa el algoritmo `gold-selection-v1` del contrato
`docs/GOLD_SET_ANNOTATION_CONTRACT.md`: elegir 20 fichas del corpus ya capturado
en DEV-208, sin descargar nada nuevo y sin modificar el corpus existente.

Deliberadamente **no** implementa la anotación. La anotación exige dos
farmacéuticos identificados y GOLD-002 sigue pendiente de decisión humana. La
selección, en cambio, no depende de esa decisión: es una función determinista
del universo, el modo, la semilla y el tamaño. Separarlas permite tener la
selección verificada y estable el día que se decidan los anotadores, sin
inventar anotadores para poder ejecutarla.

Módulo puro: no abre sockets, no escribe en disco y no importa la capa de
persistencia. Quien ejecuta aporta el universo ya leído.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from typing import Literal

ALGORITHM_VERSION = "gold-selection-v1"
GoldSelectionMode = Literal["aleatorio"]

#: GOLD-001: semilla del conjunto oro, cerrada por aprobación humana el
#: 2 de septiembre de 2026. No es un valor por defecto elegido aquí.
GOLD_SEED = 407

#: Especificación 1.1: el conjunto oro son 20 fichas.
GOLD_SIZE = 20


class GoldSelectionError(RuntimeError):
    """Entrada inválida o conflicto con una selección previa."""


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class GoldCandidate:
    """Documento del corpus elegible para el conjunto oro.

    `document_version_hash` ancla la selección a la versión concreta capturada.
    Una selección sin versión sería una selección "de la ficha", y el contrato
    exige que toda anotación pertenezca a una versión documental determinada.
    """

    nregistro: str
    document_version_hash: str

    def __post_init__(self) -> None:
        if not self.nregistro.strip():
            raise ValueError("El candidato requiere nregistro.")
        if not self.document_version_hash.strip():
            raise ValueError("El candidato requiere hash de versión documental.")


@dataclass(frozen=True)
class GoldSelectedItem:
    ordinal: int
    nregistro: str
    document_version_hash: str


@dataclass(frozen=True)
class GoldSelection:
    """Resultado de una selección, identificado por su huella de ejecución."""

    run_id: str
    algorithm_version: str
    mode: GoldSelectionMode
    seed: int
    requested_size: int
    universe_size: int
    universe_hash: str
    items: tuple[GoldSelectedItem, ...]

    def as_dict(self) -> dict[str, object]:
        """Representación canónica y ordenada, apta para `gold-selection.json`."""
        return {
            "algorithm_version": self.algorithm_version,
            "items": [
                {
                    "document_version_hash": item.document_version_hash,
                    "nregistro": item.nregistro,
                    "ordinal": item.ordinal,
                }
                for item in self.items
            ],
            "mode": self.mode,
            "requested_size": self.requested_size,
            "run_id": self.run_id,
            "seed": self.seed,
            "universe_hash": self.universe_hash,
            "universe_size": self.universe_size,
        }


def compute_universe_hash(candidates: tuple[GoldCandidate, ...]) -> str:
    """Huella del universo de entrada.

    Cubre `nregistro` **y** versión documental: dos corpus con los mismos
    registros pero versiones distintas no son el mismo universo, y tratarlos
    como tal permitiría que una selección "reproducible" se refiriese en
    realidad a documentos diferentes.
    """
    payload = json.dumps(
        sorted((item.nregistro, item.document_version_hash) for item in candidates),
        separators=(",", ":"),
    ).encode()
    return _sha256(payload)


def select_gold_set(
    candidates: tuple[GoldCandidate, ...],
    *,
    mode: GoldSelectionMode = "aleatorio",
    seed: int = GOLD_SEED,
    size: int = GOLD_SIZE,
) -> GoldSelection:
    """Selecciona el conjunto oro de forma reproducible.

    Reutiliza el modo aleatorio de `cima-sampling-v1`: ordenar por `nregistro` y
    aplicar `random.Random(seed).sample`. El orden previo importa, porque
    `sample` depende del orden de la secuencia de entrada: sin ordenar, el mismo
    corpus leído en distinto orden daría un conjunto oro distinto con la misma
    semilla.

    No se estratifica por ATC (GOLD-003): el inventario de DEV-208 carece de ese
    atributo y elegir estratos por otra vía exigiría inferir un dato ausente.
    """
    if mode != "aleatorio":
        raise GoldSelectionError(
            f"Modo de selección no soportado para el conjunto oro: {mode}"
        )
    if size <= 0:
        raise ValueError("El tamaño del conjunto oro debe ser mayor que cero.")

    nregistros = [item.nregistro for item in candidates]
    if len(set(nregistros)) != len(nregistros):
        raise GoldSelectionError("El universo contiene nregistro duplicados.")
    if size > len(candidates):
        raise GoldSelectionError(
            f"Conjunto oro solicitado {size} superior al universo {len(candidates)}."
        )

    ordered = sorted(candidates, key=lambda item: item.nregistro)
    universe_hash = compute_universe_hash(candidates)
    selected = random.Random(seed).sample(ordered, size)

    run_payload = {
        "algorithm_version": ALGORITHM_VERSION,
        "mode": mode,
        "seed": seed,
        "size": size,
        "universe_hash": universe_hash,
    }
    run_id = _sha256(
        json.dumps(run_payload, sort_keys=True, separators=(",", ":")).encode()
    )
    items = tuple(
        GoldSelectedItem(
            ordinal=ordinal,
            nregistro=item.nregistro,
            document_version_hash=item.document_version_hash,
        )
        for ordinal, item in enumerate(selected, start=1)
    )
    return GoldSelection(
        run_id=run_id,
        algorithm_version=ALGORITHM_VERSION,
        mode=mode,
        seed=seed,
        requested_size=size,
        universe_size=len(candidates),
        universe_hash=universe_hash,
        items=items,
    )


def assert_matches_existing(current: GoldSelection, previous: dict[str, object]) -> None:
    """Compara con una selección ya publicada y detiene el proceso si difiere.

    El contrato es explícito: una diferencia detiene el proceso con conflicto en
    lugar de reescribir la selección. Reescribirla invalidaría en silencio toda
    anotación hecha sobre el conjunto anterior.
    """
    if previous.get("run_id") != current.run_id:
        raise GoldSelectionError(
            "La selección difiere de la publicada: "
            f"{previous.get('run_id')} frente a {current.run_id}. "
            "No se reescribe una selección existente."
        )
    if previous.get("items") != current.as_dict()["items"]:
        raise GoldSelectionError(
            "La huella de ejecución coincide pero los elementos difieren; "
            "la selección publicada no se sobrescribe."
        )
