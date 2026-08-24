#!/usr/bin/env python3
"""Verify the local reference files used to define and test the project."""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "reference" / "raw"

EXPECTED = {
    "Catalogo_campos_clinicos_medicamentos.xlsx": "a10160ebe5c7fe0b5d2a35a12d4597c982bacdafe04cb0f8d98c437183d19eac",
    "Especialidades-CargaMaster190626.xlsx": "2117c3e33c05158dd10f81ce07424dd1ea2d0f36747faea3ad9c630b2d4ab37b",
    "Estudio carga maestros con IA.xlsx": "f3522d062e93c3bdb4366e7974edb6e3591427a375fcc7cef3ac29d70468f45e",
    "Interacciones-cargaMaster250626.xlsx": "f72d368f7590c1c41a886055f58b131305cb24c383cfa80f3028656fe351037f",
    "Medicamento-cargaMaster25062026.xlsx": "4b87aeac96ea220126c090d755fa5bfbaabe7aec304cfccb2e15537bd96cbf1b",
    "OMEPRAZOL 20 MGrelleno.xlsx": "5d11b447e5c3d9eed73b03e45d9cfe69c8cec54d89729e23a2bf95ae1564192b",
    "PrincipioActivoCargaMaster-22062026.xlsx": "89e6806b4cba7d6724533bfdc29ea834056223872385f08c080b72b965448e6c",
    "ESPEC_validador_fichas_tecnicas.md": "d951f0a23787a0355fc9f9f7e1e0c4d2e40441f7f5ef249492b4742fb29173a4",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    failed = False
    for filename, expected_hash in EXPECTED.items():
        path = RAW_DIR / filename
        if not path.exists():
            print(f"MISSING  {filename}")
            failed = True
            continue
        actual_hash = sha256(path)
        if actual_hash != expected_hash:
            print(f"CHANGED  {filename}\n         expected {expected_hash}\n         actual   {actual_hash}")
            failed = True
        else:
            print(f"OK       {filename}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
