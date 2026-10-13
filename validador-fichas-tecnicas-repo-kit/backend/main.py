"""Vercel entrypoint for the FastAPI application stored in the src layout."""

import sys
from pathlib import Path

SOURCE_DIRECTORY = Path(__file__).parent / "src"
sys.path.insert(0, str(SOURCE_DIRECTORY))

from pharma_validator_api.main import app  # noqa: E402

__all__ = ["app"]
