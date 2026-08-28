from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Protocol

from pharma_validator_api.cima_client import CimaClient, CimaResponse
from pharma_validator_api.composition_report import sample_reference
from pharma_validator_api.config import Settings
from pharma_validator_api.sampling import SamplingPersistenceError


class CorpusClient(Protocol):
    def medication(
        self, *, nregistro: str | None = None, cn: str | None = None
    ) -> CimaResponse: ...

    def content(
        self,
        *,
        nregistro: str,
        section: str | None = None,
        document_type: int = 1,
        accept: str = "application/json",
    ) -> CimaResponse: ...


def _write_exact(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as output:
            output.write(body)
    except FileExistsError:
        if path.read_bytes() != body:
            raise SamplingPersistenceError(f"Artefacto local incompatible: {path}") from None


def _artifact(
    response: CimaResponse, *, role: str, locator: str, relative_path: str
) -> dict[str, object]:
    return {
        "artifact_role": role,
        "ordinal": 1,
        "locator": locator,
        "relative_path": relative_path,
        "source_url": response.url,
        "status_code": response.status_code,
        "headers": list(response.headers),
        "content_sha256": response.content_sha256,
        "fetched_at": response.fetched_at,
    }


def capture_sample_corpus(
    *, sample_path: Path, output_dir: Path, client: CorpusClient
) -> dict[str, object]:
    run_id, nregistros = sample_reference(sample_path.read_bytes())
    documents: list[dict[str, object]] = []
    for nregistro in nregistros:
        metadata = client.medication(nregistro=nregistro)
        full_document = client.content(
            nregistro=nregistro, document_type=1, accept="application/json"
        )
        metadata_relative = f"artifacts/{nregistro}-metadata.json"
        document_relative = f"artifacts/{nregistro}-ft.json"
        _write_exact(output_dir / metadata_relative, metadata.body)
        _write_exact(output_dir / document_relative, full_document.body)
        documents.append(
            {
                "nregistro": nregistro,
                "document_type": 1,
                "source_version": None,
                "artifacts": [
                    _artifact(
                        metadata,
                        role="metadata",
                        locator="medicamento",
                        relative_path=metadata_relative,
                    ),
                    _artifact(
                        full_document,
                        role="full_document",
                        locator="all-sections",
                        relative_path=document_relative,
                    ),
                ],
            }
        )
    manifest = {
        "schema_version": "1.0.0",
        "corpus_id": f"cima-sample-{run_id}",
        "corpus_kind": "downloaded_cima",
        "description": (
            "Corpus CIMA descargado para una muestra aprobada; "
            "source_version se conserva sin inferir."
        ),
        "documents": documents,
    }
    body = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    _write_exact(output_dir / "manifest.json", body)
    return {
        "documents": len(documents),
        "artifacts": len(documents) * 2,
        "manifest_sha256": hashlib.sha256(body).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Descarga una muestra CIMA a corpus offline")
    parser.add_argument("--sample", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    settings = Settings()
    with CimaClient(
        base_url=settings.cima_base_url,
        cache_dir=settings.cima_cache_dir,
        timeout_seconds=settings.cima_timeout_seconds,
        requests_per_second=settings.cima_requests_per_second,
        max_retries=settings.cima_max_retries,
        backoff_seconds=settings.cima_backoff_seconds,
        max_retry_delay_seconds=settings.cima_max_retry_delay_seconds,
    ) as client:
        summary = capture_sample_corpus(
            sample_path=args.sample, output_dir=args.output_dir, client=client
        )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
