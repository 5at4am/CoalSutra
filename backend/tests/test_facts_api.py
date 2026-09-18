"""API tests for the facts and conflicts listing endpoints."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models import ConflictFlag, Document, ExtractedFact
from app.models.enums import ConflictStatus, DocumentStatus, SourceType


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client, factory

    app.dependency_overrides.pop(get_db, None)
    engine.dispose()


def _seed_fact(factory, document_id, entity="coal_reserve", value="1240") -> int:
    with factory() as s:
        fact = ExtractedFact(
            document_id=document_id,
            entity=entity,
            value=value,
            unit="MT",
            date_reference=date(2019, 1, 1),
            page_number=1,
            raw_snippet=f"{entity} {value} MT",
            confidence=0.95,
        )
        s.add(fact)
        s.commit()
        return fact.id


def _seed_document(factory) -> int:
    with factory() as s:
        doc = Document(
            filename="a.pdf",
            source_type=SourceType.digital_pdf,
            status=DocumentStatus.processed,
            raw_file_path="/tmp/a.pdf",
        )
        s.add(doc)
        s.commit()
        return doc.id


def test_list_facts_empty(client):
    test_client, _ = client
    resp = test_client.get("/api/v1/facts")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_facts_and_filter_by_entity(client):
    test_client, factory = client
    doc_id = _seed_document(factory)
    _seed_fact(factory, doc_id, entity="coal_reserve", value="1240")
    _seed_fact(factory, doc_id, entity="ash_content", value="18")

    all_resp = test_client.get("/api/v1/facts").json()
    assert len(all_resp) == 2

    entity_resp = test_client.get("/api/v1/facts?entity=ash_content").json()
    assert len(entity_resp) == 1
    assert entity_resp[0]["entity"] == "ash_content"
    assert entity_resp[0]["value"] == "18"

    missing = test_client.get("/api/v1/facts?entity=not_a_thing").json()
    assert missing == []


def test_list_facts_filter_by_document(client):
    test_client, factory = client
    doc_a = _seed_document(factory)
    doc_b = _seed_document(factory)
    fact_a = _seed_fact(factory, doc_a, value="1240")
    _seed_fact(factory, doc_b, value="938")

    resp = test_client.get(f"/api/v1/facts?document_id={doc_a}").json()
    assert len(resp) == 1
    assert resp[0]["id"] == fact_a
    assert resp[0]["document_id"] == doc_a
    assert resp[0]["page_number"] == 1
    assert resp[0]["date_reference"] == "2019-01-01"


def test_list_conflicts_and_filter_by_status(client):
    test_client, factory = client
    doc_a = _seed_document(factory)
    doc_b = _seed_document(factory)
    fact_a = _seed_fact(factory, doc_a, value="1240")
    fact_b = _seed_fact(factory, doc_b, value="938")

    with factory() as s:
        s.add(
            ConflictFlag(
                fact_a_id=fact_a,
                fact_b_id=fact_b,
                reason="coal_reserve 2019 differs",
                status=ConflictStatus.open,
            )
        )
        s.add(
            ConflictFlag(
                fact_a_id=fact_a,
                fact_b_id=fact_b,
                reason="old resolved",
                status=ConflictStatus.resolved,
                resolved_by="reviewer@cil",
            )
        )
        s.commit()

    all_resp = test_client.get("/api/v1/conflicts").json()
    assert len(all_resp) == 2

    open_resp = test_client.get("/api/v1/conflicts?status=open").json()
    assert len(open_resp) == 1
    assert open_resp[0]["status"] == "open"
    assert open_resp[0]["fact_a_id"] == fact_a
    assert open_resp[0]["fact_b_id"] == fact_b

    resolved_resp = test_client.get("/api/v1/conflicts?status=resolved").json()
    assert resolved_resp[0]["resolved_by"] == "reviewer@cil"


def test_conflicts_filter_accepts_only_valid_statuses(client):
    test_client, _ = client
    assert test_client.get("/api/v1/conflicts?status=bogus").status_code == 422