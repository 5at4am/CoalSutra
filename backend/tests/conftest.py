from __future__ import annotations

import os
from pathlib import Path

import pytest

# Hermetic test suite: force the offline pipeline before app modules import,
# so extraction/embeddings never depend on a live (or real-keyed) provider.
# Auth is disabled so the bulk of the suite exercises services, not the login
# gate; auth behaviour is covered explicitly in test_auth.py.
os.environ["LLM_API_KEY"] = ""
os.environ["EMBEDDING_PROVIDER"] = "hash"
os.environ["AUTH_ENABLED"] = "false"

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(autouse=True)
def _no_lifespan_resume(monkeypatch):
    """Never let the app startup hook touch the shared/dev database in tests.

    The FastAPI lifespan calls `resume_stale_jobs()` against the default engine;
    each API test overrides `get_db`, so the startup resume must be a no-op here
    (its behaviour is covered directly in test_ingestion_jobs).
    """
    import app.main

    def _noop(*args, **kwargs):
        return {"requeued": 0, "reset": 0}

    monkeypatch.setattr(app.main, "resume_stale_jobs", _noop)


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