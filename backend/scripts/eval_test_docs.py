"""Run real test_docs through the pipeline on a throwaway DB and print results."""
import os, sys, shutil, tempfile

os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(
    tempfile.gettempdir(), "testdocs_eval.db"
)
if os.path.exists(os.path.join(tempfile.gettempdir(), "testdocs_eval.db")):
    os.remove(os.path.join(tempfile.gettempdir(), "testdocs_eval.db"))
os.environ["EMBEDDING_PROVIDER"] = "hash"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import Base, SessionLocal, engine
from app.models import Document, ExtractedFact, DocumentPage, ConflictFlag
from app.models.enums import DocumentStatus, SourceType
from app.services.ingestion.orchestrator import ingest_document

BASE = r"C:\Users\PC\Desktop\SIH\26023\Test_docs"
FILES = [
    "Barkhola_Coal_Block_Reserve_Estimation_Summary_2026.pdf",
    "geological_survey_report_scan.pdf",
    "production_table_scan.png",
    "ChatGPT Image Sep 18, 2026, 03_48_07 PM.png",
    "ChatGPT Image Sep 18, 2026, 03_49_28 PM.png",
]

Base.metadata.create_all(engine)
session = SessionLocal()

for name in FILES:
    path = os.path.join(BASE, name)
    doc = Document(filename=name, source_type=SourceType.digital_pdf, status=DocumentStatus.pending, raw_file_path=path)
    session.add(doc)
    session.commit()
    did = doc.id
    ingest_document(did, session_factory=SessionLocal)
    d = session.get(Document, did)
    print("=" * 100)
    print(f"FILE: {name}  -> status={d.status} source_type={d.source_type} pages={len(session.query(DocumentPage).filter_by(document_id=did).all())}")
    facts = session.query(ExtractedFact).filter_by(document_id=did).all()
    print(f"FACTS: {len(facts)}")
    for f in facts:
        print(f"   {f.entity} = {f.value}{f.unit or ''} @ {f.date_reference} p{f.page_number} conf={f.confidence}")
        print(f"       snippet: {(f.raw_snippet or '')[:140]}")

session.close()
print("=" * 100)
print("DONE")