from __future__ import annotations

import os
from pathlib import Path

import pytest

# Hermetic test suite: force the offline pipeline before app modules import,
# so extraction/embeddings never depend on a live (or real-keyed) provider.
os.environ["LLM_API_KEY"] = ""
os.environ["EMBEDDING_PROVIDER"] = "hash"

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture()
def digital_pdf() -> Path:
    return FIXTURES_DIR / "digital_sample.pdf"


@pytest.fixture()
def scanned_pdf() -> Path:
    return FIXTURES_DIR / "scanned_sample.pdf"


@pytest.fixture()
def sample_image() -> Path:
    return FIXTURES_DIR / "sample_image.png"


@pytest.fixture()
def sample_csv() -> Path:
    return FIXTURES_DIR / "sample.csv"