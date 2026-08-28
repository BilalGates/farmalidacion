import hashlib
import json
from pathlib import Path

import pytest

from pharma_validator_api.cima_client import CimaResponse
from pharma_validator_api.corpus_capture import capture_sample_corpus
from pharma_validator_api.offline_corpus import verify_offline_corpus
from pharma_validator_api.sampling import SamplingPersistenceError


def response(nregistro: str, kind: str) -> CimaResponse:
    body = json.dumps({"nregistro": nregistro, "kind": kind}).encode()
    return CimaResponse(
        url=f"https://cima.example.test/{kind}?nregistro={nregistro}",
        status_code=200,
        headers=(("Content-Type", "application/json"),),
        body=body,
        content_sha256=hashlib.sha256(body).hexdigest(),
        fetched_at="2026-08-28T10:00:00+00:00",
        from_cache=False,
    )


class FakeClient:
    def medication(self, *, nregistro: str | None = None, cn: str | None = None) -> CimaResponse:
        assert nregistro is not None and cn is None
        return response(nregistro, "metadata")

    def content(
        self,
        *,
        nregistro: str,
        section: str | None = None,
        document_type: int = 1,
        accept: str = "application/json",
    ) -> CimaResponse:
        assert section is None and document_type == 1 and accept == "application/json"
        return response(nregistro, "full-document")


def write_sample(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "run_id": "run-1",
                "requested_size": 2,
                "items": [
                    {"ordinal": 1, "nregistro": "1"},
                    {"ordinal": 2, "nregistro": "2"},
                ],
            }
        ),
        encoding="utf-8",
    )


def test_capture_is_reproducible_and_verifiable(tmp_path: Path) -> None:
    sample = tmp_path / "sample.json"
    write_sample(sample)
    output = tmp_path / "corpus"
    first = capture_sample_corpus(sample_path=sample, output_dir=output, client=FakeClient())
    second = capture_sample_corpus(sample_path=sample, output_dir=output, client=FakeClient())
    assert first == second
    assert first["documents"] == 2
    assert verify_offline_corpus(output).manifest.corpus_kind == "downloaded_cima"


def test_capture_never_overwrites_existing_artifact(tmp_path: Path) -> None:
    sample = tmp_path / "sample.json"
    write_sample(sample)
    target = tmp_path / "corpus/artifacts/1-metadata.json"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"distinto")
    with pytest.raises(SamplingPersistenceError, match="Artefacto local incompatible"):
        capture_sample_corpus(
            sample_path=sample, output_dir=tmp_path / "corpus", client=FakeClient()
        )
    assert not (tmp_path / "corpus/manifest.json").exists()
