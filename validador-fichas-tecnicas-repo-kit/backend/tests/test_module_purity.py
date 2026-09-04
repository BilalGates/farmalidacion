"""Los módulos de decisión son puros (Fases 4 y 5).

Sus contratos afirman que no abren sockets, no tocan disco y no dependen de
hardware. Una afirmación en un documento envejece; esta suite la comprueba.

Importa además para la restricción de la especificación 8.3: no hay salida a
internet, y toda la inferencia se ejecuta dentro de la red del centro. Un módulo
que abriera una conexión al importarse rompería esa garantía en silencio.
"""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

PURE_MODULES = (
    "block_editing",
    "evidence_verification",
    "extraction_batches",
    "extractor",
    "gold_annotations",
    "gold_selection",
    "guided_schema",
    "prefill_policy",
    "reviewer_identity",
    "section_grouping",
    "time_measurement",
    "validation_states",
)


@pytest.mark.parametrize("module_name", PURE_MODULES)
def test_module_imports_without_opening_a_socket(module_name: str) -> None:
    """Se importa en un intérprete aparte, no con `importlib.reload`.

    Recargar el módulo en este proceso sustituiría sus clases por otras nuevas,
    y las excepciones que capturan las demás suites dejarían de reconocerse:
    una prueba de pureza no puede contaminar el estado global de la sesión.
    """
    program = (
        "import socket, sys\n"
        "def deny(*args, **kwargs):\n"
        "    raise AssertionError('socket')\n"
        "socket.socket = deny\n"
        f"import pharma_validator_api.{module_name}\n"
    )
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", program],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
        check=False,
    )
    assert result.returncode == 0, (
        f"{module_name} falló al importarse con sockets bloqueados: {result.stderr}"
    )


def module_source(module_name: str) -> str:
    return (
        Path(__file__).resolve().parents[1]
        / "src"
        / "pharma_validator_api"
        / f"{module_name}.py"
    ).read_text(encoding="utf-8")


@pytest.mark.parametrize("module_name", PURE_MODULES)
def test_module_does_not_call_filesystem_primitives(module_name: str) -> None:
    """Ninguno escribe en disco: sus salidas son valores, no ficheros.

    Se inspeccionan las llamadas del árbol sintáctico, no subcadenas del
    fuente: `replace(` aparece legítimamente como `dataclasses.replace`.
    """
    forbidden = {"open", "mkdir", "write_text", "write_bytes", "rmtree", "unlink"}
    called: set[str] = set()
    for node in ast.walk(ast.parse(module_source(module_name))):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        if isinstance(target, ast.Name):
            called.add(target.id)
        elif isinstance(target, ast.Attribute):
            called.add(target.attr)
    offending = called & forbidden
    assert offending == set(), f"{module_name} accede a disco: {sorted(offending)}"


FORBIDDEN_IMPORTS = frozenset(
    {"sqlalchemy", "httpx", "requests", "urllib", "socket", "pathlib", "shutil"}
)


def imported_roots(module_name: str) -> set[str]:
    """Raíces realmente importadas, según el árbol sintáctico.

    Buscar subcadenas en el fuente da falsos positivos: `requests` aparece como
    nombre de campo en varios módulos sin que se importe la librería.
    """
    tree = ast.parse(module_source(module_name))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
            if node.module.startswith("pharma_validator_api."):
                roots.add(node.module)
    return roots


@pytest.mark.parametrize("module_name", PURE_MODULES)
def test_module_does_not_import_database_or_http_layers(module_name: str) -> None:
    roots = imported_roots(module_name)
    offending = roots & FORBIDDEN_IMPORTS
    assert offending == set(), f"{module_name} importa {sorted(offending)}."
    assert "pharma_validator_api.database" not in roots
    assert "pharma_validator_api.models" not in roots
