"""Genera el conjunto DEMO de la vertical de revisión.

Alcance y límites, explícitos por diseño:

- Los **nombres de campo y de bloque** proceden del catálogo real de 353
  definiciones. No se inventa semántica: si un campo no está en el catálogo, no
  aparece aquí.
- Los **valores** son de demostración, no importados de los maestros ni de CIMA.
  Cada identificador externo declara el sistema fuente `demo_showcase` y el
  fixture lleva una `provenance_note`, de modo que un dato DEMO no pueda
  confundirse más tarde con uno real.
- Las discrepancias entre fuentes se representan como **afirmaciones separadas
  con procedencia distinta**, nunca como un valor ya elegido. Sin matriz de
  prioridad cargada, el motor de ADR-0007 las deja sin resolver.
- No se modifica ningún fichero original de referencia.

El fichero generado es determinista: identificadores fijos y orden estable, de
modo que dos ejecuciones produzcan bytes idénticos.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

SCHEMA_VERSION = "1.0.0"
PROVENANCE_NOTE = (
    "DATOS DE DEMOSTRACIÓN. Los nombres de campo y bloque proceden del catálogo "
    "real; los valores son de demostración y no provienen de los maestros ni de "
    "CIMA. No deben usarse como evidencia clínica ni exportarse."
)
DOCUMENT_ID = "10000000-0000-4000-8000-000000000001"
VERSION_MASTER = "10000000-0000-4000-8000-000000000010"
VERSION_CIMA = "10000000-0000-4000-8000-000000000011"
VERSION_FT = "10000000-0000-4000-8000-000000000012"


def _uid(prefix: int, index: int) -> str:
    return f"10000000-0000-4000-8000-{prefix:04d}{index:08d}"


class Builder:
    """Acumula filas del modelo canónico manteniendo identificadores estables."""

    def __init__(self) -> None:
        self.fragments: list[dict[str, object]] = []
        self.records: list[dict[str, object]] = []
        self.identifiers: list[dict[str, object]] = []
        self.links: list[dict[str, object]] = []
        self.blocks: list[dict[str, object]] = []
        self.values: list[dict[str, object]] = []
        self.provenances: list[dict[str, object]] = []

    def fragment(self, version_id: str, locator: str, literal: str) -> str:
        identifier = _uid(1, len(self.fragments) + 1)
        self.fragments.append(
            {
                "id": identifier,
                "document_version_id": version_id,
                "locator_type": "demo_locator",
                "locator": locator,
                "literal_text": literal,
            }
        )
        return identifier

    def record(self, external_id: str) -> str:
        identifier = _uid(2, len(self.records) + 1)
        self.records.append({"id": identifier, "entity_type": "medication"})
        self.identifiers.append(
            {
                "id": _uid(3, len(self.identifiers) + 1),
                "target_record_id": identifier,
                "source_system": "demo_showcase",
                "source_identifier": external_id,
                "source_version": "demo-v1",
            }
        )
        for version_id in (VERSION_MASTER, VERSION_CIMA, VERSION_FT):
            self.links.append(
                {
                    "id": _uid(4, len(self.links) + 1),
                    "document_version_id": version_id,
                    "target_record_id": identifier,
                    "link_type": "demo_source",
                }
            )
        return identifier

    def block(
        self, record_id: str, block_type: str, ordinal: int, fragment: str | None
    ) -> str:
        identifier = _uid(5, len(self.blocks) + 1)
        self.blocks.append(
            {
                "id": identifier,
                "target_record_id": record_id,
                "block_type": block_type,
                "ordinal": ordinal,
                "source_fragment_id": fragment,
            }
        )
        return identifier

    def value(
        self,
        block_id: str,
        field_name: str,
        literal: str | None,
        observed_type: str,
        logical_state: str,
        sources: list[tuple[str, str]],
    ) -> str:
        """Registra un valor y **todas** sus procedencias.

        `sources` es una lista de `(rol, fragmento)`. Varias entradas con el
        mismo valor son coincidencia entre fuentes; el desacuerdo se modela como
        valores distintos con procedencia distinta, nunca eligiendo uno.
        """
        identifier = _uid(6, len(self.values) + 1)
        self.values.append(
            {
                "id": identifier,
                "block_instance_id": block_id,
                "field_name": field_name,
                "literal_value": literal,
                "observed_type": observed_type,
                "logical_state": logical_state,
            }
        )
        for role, fragment in sources:
            self.provenances.append(
                {
                    "id": _uid(7, len(self.provenances) + 1),
                    "field_value_id": identifier,
                    "source_fragment_id": fragment,
                    "provenance_role": role,
                }
            )
        return identifier


#: Registros DEMO. Los nombres de bloque y campo son los del catálogo real.
DEMO_RECORDS: list[dict[str, str]] = [
    {
        "external_id": "DEMO-0001",
        "name": "Omeprazol 20 mg cápsulas duras",
        "ingredient": "omeprazol",
        "atc": "A02BC01",
        "dose": "20 mg",
        "cima_dose": "20 mg",
        "form": "Cápsula dura gastrorresistente",
    },
    {
        "external_id": "DEMO-0002",
        "name": "Metotrexato 2,5 mg comprimidos",
        "ingredient": "metotrexato",
        "atc": "L01BA01",
        "dose": "2,5 mg",
        # Discrepancia deliberada entre maestro y CIMA: la interfaz debe
        # mostrarla sin elegir, porque la prioridad por campo no está cargada.
        "cima_dose": "2,5 mg/comprimido",
        "form": "Comprimido",
    },
    {
        "external_id": "DEMO-0003",
        "name": "Adalimumab 40 mg solución inyectable",
        "ingredient": "adalimumab",
        "atc": "L04AB04",
        "dose": "40 mg",
        "cima_dose": "40 mg",
        "form": "Solución inyectable en pluma precargada",
    },
    {
        "external_id": "DEMO-0004",
        "name": "Amoxicilina 500 mg cápsulas",
        "ingredient": "amoxicilina",
        "atc": "J01CA04",
        "dose": "500 mg",
        "cima_dose": "500 mg",
        "form": "Cápsula dura",
    },
    {
        "external_id": "DEMO-0005",
        "name": "Enalapril 10 mg comprimidos",
        "ingredient": "enalapril",
        "atc": "C09AA02",
        "dose": "10 mg",
        "cima_dose": "10 mg",
        "form": "Comprimido",
    },
]


def build() -> dict[str, object]:
    builder = Builder()
    for entry in DEMO_RECORDS:
        external_id = entry["external_id"]
        record_id = builder.record(external_id)
        master = builder.fragment(
            VERSION_MASTER,
            f"maestro/{external_id}",
            f"Fila de maestro DEMO {external_id}",
        )
        cima = builder.fragment(
            VERSION_CIMA, f"cima/{external_id}", f"Metadato CIMA DEMO {external_id}"
        )
        ficha = builder.fragment(
            VERSION_FT,
            f"ficha-tecnica/{external_id}#2",
            f"Apartado 2 de ficha técnica DEMO para {external_id}",
        )

        identity = builder.block(record_id, "Medicamento - General", 1, master)
        builder.value(
            identity,
            "ME_DESCRIPCION",
            entry["name"],
            "CHAR(100)",
            "valued",
            [("master_baseline", master)],
        )
        builder.value(
            identity,
            "ATC",
            entry["atc"],
            "CHAR(50)",
            "valued",
            [("master_baseline", master), ("cima_structured", cima)],
        )
        builder.value(
            identity,
            "FORMAFARMA",
            entry["form"],
            "CHAR(100)",
            "valued",
            [("cima_structured", cima)],
        )
        # Campo sin dato en ninguna fuente: se declara ausente, no vacío.
        builder.value(
            identity,
            "RECOMENPRESCRIP",
            None,
            "CHAR(4000)",
            "empty",
            [("master_baseline", master)],
        )

        composition = builder.block(record_id, "Composición", 1, master)
        builder.value(
            composition,
            "PA_DESCRIPCION",
            entry["ingredient"],
            "CHAR(50)",
            "valued",
            [("master_baseline", master), ("technical_sheet", ficha)],
        )
        builder.value(
            composition,
            "CANTIDAD",
            entry["dose"],
            "CHAR(50)",
            "valued",
            [("master_baseline", master)],
        )
        if entry["cima_dose"] != entry["dose"]:
            # Segunda afirmación, con su propia procedencia. No sustituye a la
            # anterior: ambas quedan visibles y la resolución es humana.
            builder.value(
                composition,
                "CANTIDAD",
                entry["cima_dose"],
                "CHAR(50)",
                "valued",
                [("cima_structured", cima)],
            )

        # Segunda ocurrencia de composición: excipiente. Bloque repetible con
        # identidad propia, nunca concatenado con el anterior.
        excipient = builder.block(record_id, "Composición", 2, ficha)
        builder.value(
            excipient,
            "EX_DESCRIPCION",
            "Lactosa monohidrato",
            "CHAR(100)",
            "valued",
            [("technical_sheet", ficha)],
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "provenance_note": PROVENANCE_NOTE,
        "source_documents": [
            {
                "id": DOCUMENT_ID,
                "source_type": "demo_showcase",
                "name": "Conjunto DEMO de la vertical de revisión",
            }
        ],
        "source_document_versions": [
            {
                "id": VERSION_MASTER,
                "document_id": DOCUMENT_ID,
                "content_hash": "0" * 64,
                "source_version": "demo-maestro-v1",
                "source_locator": "demo://maestro",
                "acquired_at": "2026-09-03T00:00:00",
            },
            {
                "id": VERSION_CIMA,
                "document_id": DOCUMENT_ID,
                "content_hash": "1" * 64,
                "source_version": "demo-cima-v1",
                "source_locator": "demo://cima",
                "acquired_at": "2026-09-03T00:00:00",
            },
            {
                "id": VERSION_FT,
                "document_id": DOCUMENT_ID,
                "content_hash": "2" * 64,
                "source_version": "demo-ficha-v1",
                "source_locator": "demo://ficha-tecnica",
                "acquired_at": "2026-09-03T00:00:00",
            },
        ],
        "source_fragments": builder.fragments,
        "target_records": builder.records,
        "external_identifiers": builder.identifiers,
        "document_record_links": builder.links,
        "block_instances": builder.blocks,
        "field_values": builder.values,
        "value_provenances": builder.provenances,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera el conjunto DEMO.")
    parser.add_argument(
        "--output", type=Path, default=Path("data/examples/showcase-demo.json")
    )
    args = parser.parse_args()
    payload = json.dumps(build(), ensure_ascii=False, indent=2) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload, encoding="utf-8")
    print(f"Fixture DEMO escrito en {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
