"""Manifiesto de exportacion (DEV-604/605).

Una entrega sin manifiesto no es verificable: quien la recibe no puede saber
que perfil la produjo, cuantas filas contiene ni si el fichero llego intacto.

El manifiesto describe la exportacion; **no la certifica clinicamente**. Que un
fichero este bien formado no dice nada sobre si sus valores estan validados: eso
lo gobierna el estado de revision de cada campo, no este modulo.

Modulo puro: sin base de datos, sin reloj y sin red. La marca de tiempo se
recibe como dato para que el manifiesto sea reproducible en pruebas.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

from pharma_validator_api.export_engine import ExportProfile, ExportResult

#: Version del formato del propio manifiesto. Cambiarla es un cambio de contrato.
MANIFEST_VERSION = "1"


@dataclass(frozen=True)
class ExportManifest:
    """Descripcion verificable de una exportacion concreta."""

    manifest_version: str
    profile_name: str
    profile_format: str
    provider_accepted: bool
    row_count: int
    column_names: tuple[str, ...]
    encoding: str
    delimiter: str
    decimal_separator: str
    content_sha256: str
    byte_size: int
    generated_at: str
    incident_count: int
    # Contexto de origen. Opcional porque una exportacion tecnica puede no
    # proceder de un lote de revision.
    source_note: str = ""

    def to_json(self) -> str:
        """JSON canonico: claves ordenadas, para que su hash sea estable."""
        return json.dumps(
            {
                "manifest_version": self.manifest_version,
                "profile_name": self.profile_name,
                "profile_format": self.profile_format,
                "provider_accepted": self.provider_accepted,
                "row_count": self.row_count,
                "column_names": list(self.column_names),
                "encoding": self.encoding,
                "delimiter": self.delimiter,
                "decimal_separator": self.decimal_separator,
                "content_sha256": self.content_sha256,
                "byte_size": self.byte_size,
                "generated_at": self.generated_at,
                "incident_count": self.incident_count,
                "source_note": self.source_note,
            },
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    @property
    def manifest_sha256(self) -> str:
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()


def build_manifest(
    profile: ExportProfile,
    result: ExportResult,
    *,
    generated_at: datetime,
    source_note: str = "",
) -> ExportManifest:
    """Construye el manifiesto de una exportacion ya producida.

    Se exige el resultado real, no los datos de entrada: el manifiesto describe
    lo que se va a entregar, y recalcularlo por separado permitiria que ambos
    dejaran de coincidir.
    """
    return ExportManifest(
        manifest_version=MANIFEST_VERSION,
        profile_name=profile.name,
        profile_format=profile.fmt,
        provider_accepted=profile.provider_accepted,
        row_count=result.row_count,
        column_names=tuple(c.name for c in profile.columns),
        encoding=profile.encoding,
        delimiter=profile.delimiter,
        decimal_separator=profile.decimal_separator,
        content_sha256=result.checksum_sha256,
        byte_size=len(result.content),
        generated_at=generated_at.isoformat(),
        incident_count=len(result.incidents),
        source_note=source_note,
    )


def verify(manifest: ExportManifest, content: bytes) -> None:
    """Comprueba que un fichero corresponde a su manifiesto.

    Se comprueban tamano y hash. Un fallo se informa como error y no se
    intenta reparar: un contenido que no cuadra con su manifiesto no es una
    version aproximada de la entrega, es otra cosa.
    """
    if len(content) != manifest.byte_size:
        raise ValueError(
            f"El contenido mide {len(content)} bytes y el manifiesto declara "
            f"{manifest.byte_size}."
        )
    digest = hashlib.sha256(content).hexdigest()
    if digest != manifest.content_sha256:
        raise ValueError(
            "El contenido no coincide con el hash declarado en el manifiesto."
        )
