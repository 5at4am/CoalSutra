"""Seed a demo-ready database with synthetic CIL/CMPDI-style documents.

Runs the REAL pipeline (route -> extract -> normalize -> validate -> embed) on
three generated sample files, exactly as a live upload would:

  1. ``Jharia_Reserve_Final_2019.pdf``  born-digital PDF  -> digital_pdf
  2. ``Bokaro_Scan_Quality_2021.pdf``   scanned-quality   -> scanned_pdf
  3. ``Production_Reserves_2025.csv``   spreadsheet       -> spreadsheet

All content below is synthetic (clearly non-CIL data): plausible reserve,
production, ash/moisture and overburden figures so every downstream screen has
something legible. A deliberate cross-source conflict is seeded — coal_reserve
2019 is 1240 MT in the digital PDF but 1125 MT in the spreadsheet — so the
Review Queue has a real open conflict to resolve (the system never silently
overwrites a stored figure).

The scanned-quality PDF ships with its OCR text layer baked in so it ingests
without a tesseract/poppler binary. After ingestion its ``source_type`` is
rewritten to ``scanned_pdf`` to reflect the source intent; to exercise *true*
OCR instead, drop a real image-only scan here and set ``OCR_PROVIDER``.

Usage (from ``backend/``):

    python scripts/seed_demo_data.py                    # uses DATABASE_URL
    python scripts/seed_demo_data.py --url sqlite:///data/seed_demo/demo.db
    python scripts/seed_demo_data.py --reset            # wipe DB, seed fresh

For Postgres run ``alembic upgrade head`` once first (the script mirrors the
existing tables idempotently via create_all).
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import Base  # noqa: E402
from app.models import (  # noqa: E402
    ConflictFlag,
    Document,
    DocumentChunk,
    ExtractedFact,
    TopicRun,
)
from app.models.enums import ConflictStatus, DocumentStatus, SourceType  # noqa: E402
from app.services.ingestion.orchestrator import ingest_document  # noqa: E402
from app.services.reporting.generator import generate_report  # noqa: E402
from app.services.topics.topic_model import run_topic_model  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname).1s %(name)s: %(message)s")

DATA_DIR = BACKEND_DIR / "data" / "seed_demo"

SEED_FILENAMES = (
    "Jharia_Reserve_Final_2019.pdf",
    "Bokaro_Scan_Quality_2021.pdf",
    "Production_Reserves_2025.csv",
)


# --- synthetic content -----------------------------------------------------


def _write_digital_pdf(path: Path) -> None:
    """Born-digital PDF (reportlab text layer)."""
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path))
    c.setTitle("Jharia Final Reserve Assessment (synthetic demo)")
    c.setFont("Helvetica-Bold", 13)
    c.drawString(50, 760, "Jharia Coalfield - Final Reserve Assessment")
    c.setFont("Helvetica", 11)
    lines_page1 = [
        "The proved coal reserve of Jharia block is 1240 million tonnes in 2019.",
        "The annual extraction plan for the block was published in 2019.",
    ]
    start_y = 725
    for i, line in enumerate(lines_page1):
        c.drawString(50, start_y - i * 18, line)
    c.showPage()

    c.setFont("Helvetica-Bold", 13)
    c.drawString(50, 760, "Production trend (synthetic)")
    c.setFont("Helvetica", 11)
    lines_page2 = [
        "Coal production averaged 38.5 million tonnes in 2026.",
        "Installed mine capacity stands at 48.0 million tonnes in 2026.",
        "Despatch for the quarter was 41.2 million tonnes in 2026.",
    ]
    for i, line in enumerate(lines_page2):
        c.drawString(50, start_y - i * 18, line)
    c.showPage()
    c.save()


def _write_scanned_pdf(path: Path) -> None:
    """Scanned-quality PDF: digital-copy layout with the OCR text layer baked in."""
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path))
    c.setTitle("Bokaro Quality Report - scanned copy (synthetic demo)")
    c.setFont("Helvetica-Bold", 13)
    c.drawString(50, 760, "SCANNED COPY - BOKARO FIELD QUALITY REPORT")
    c.setFont("Helvetica", 11)
    lines_page1 = [
        "Ash content of the Bokaro seam was measured at 18.5 per cent in 2021.",
        "Moisture content of the Bokaro seam measured 9.2 per cent in 2021.",
    ]
    start_y = 725
    for i, line in enumerate(lines_page1):
        c.drawString(50, start_y - i * 18, line)
    c.showPage()

    c.setFont("Helvetica-Bold", 13)
    c.drawString(50, 760, "SCANNED COPY - continued")
    c.setFont("Helvetica", 11)
    lines_page2 = [
        "The overburden ratio at Bokaro North is 1.28 in 2021.",
        "Coal production at Bokaro West reached 21.4 million tonnes in 2021.",
    ]
    for i, line in enumerate(lines_page2):
        c.drawString(50, start_y - i * 18, line)
    c.showPage()
    c.save()


def _write_spreadsheet(path: Path) -> None:
    """Spreadsheet (CSV) with a reserve/production table."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Year", "Block", "Coal production (t)", "Coal reserve (MT)"])
        # 2019 reserve figure (1125 MT) deliberately conflicts with the digital PDF.
        writer.writerow(["2019", "Jharia", "1420000", "1125"])
        writer.writerow(["2025", "Khas Jageshwar", "520000", "1625"])
        writer.writerow(["2025", "Barka Sayal", "460000", "860"])


# --- seeding ---------------------------------------------------------------


def _generate_files() -> dict[str, Path]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    paths = {
        "digital": DATA_DIR / SEED_FILENAMES[0],
        "scanned": DATA_DIR / SEED_FILENAMES[1],
        "spreadsheet": DATA_DIR / SEED_FILENAMES[2],
    }
    _write_digital_pdf(paths["digital"])
    _write_scanned_pdf(paths["scanned"])
    _write_spreadsheet(paths["spreadsheet"])
    return paths


def _ingest_document(factory, filename: str, path: Path, provisional: SourceType) -> Document:
    with factory() as session:
        doc = Document(
            filename=filename,
            source_type=provisional,
            status=DocumentStatus.pending,
            raw_file_path=str(path),
        )
        session.add(doc)
        session.commit()
        doc_id = doc.id

    ingest_document(doc_id, session_factory=factory)

    with factory() as session:
        return session.get(Document, doc_id)


def _summarize(factory, doc_ids: list[int]) -> None:
    with factory() as session:
        for doc_id in doc_ids:
            doc = session.get(Document, doc_id)
            facts = (
                session.query(func.count(ExtractedFact.id))
                .filter(ExtractedFact.document_id == doc_id)
                .scalar()
                or 0
            )
            chunks = (
                session.query(func.count(DocumentChunk.id))
                .filter(DocumentChunk.document_id == doc_id)
                .scalar()
                or 0
            )
            flags = (
                session.query(ConflictFlag)
                .join(ExtractedFact, ConflictFlag.fact_a_id == ExtractedFact.id)
                .filter(ExtractedFact.document_id == doc_id)
                .filter(ConflictFlag.status == ConflictStatus.open)
                .count()
            )
            print(
                f"  doc {doc_id:<4} {doc.filename:<32} "
                f"{doc.source_type.value:<12} status={doc.status.value:<9} "
                f"facts={facts:<3} chunks={chunks:<3} open_flags={flags}"
            )

        open_conflicts = (
            session.query(func.count(ConflictFlag.id))
            .filter(ConflictFlag.status == ConflictStatus.open)
            .scalar()
            or 0
        )
        drafted = (
            session.query(func.count(ExtractedFact.id))
            .join(Document)
            .filter(Document.filename.in_(SEED_FILENAMES))
            .scalar()
        )
        print(f"  total open conflicts to review ......... {open_conflicts}")
        print(f"  seeded facts across seed documents .... {drafted}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default=settings.DATABASE_URL,
        help="SQLAlchemy URL (default: DATABASE_URL / %(default)s)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="drop all tables and start with a clean demo database",
    )
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    engine = create_engine(args.url)
    if args.reset:
        Base.metadata.drop_all(engine)
        print(f"[seed] dropped all tables on {args.url}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    print(f"[seed] database: {args.url}")
    paths = _generate_files()
    print("[seed] generated synthetic documents:")

    scanned = _ingest_document(
        factory, SEED_FILENAMES[1], paths["scanned"], SourceType.scanned_pdf
    )
    # Reclassify() inside the orchestrator sees the baked-in text layer and calls
    # it digital; rewrite to scanned_pdf to reflect the scanned source intent.
    with factory() as session:
        stored = session.get(Document, scanned.id)
        stored.source_type = SourceType.scanned_pdf
        session.commit()

    spreadsheet = _ingest_document(
        factory, SEED_FILENAMES[2], paths["spreadsheet"], SourceType.spreadsheet
    )
    digital = _ingest_document(
        factory, SEED_FILENAMES[0], paths["digital"], SourceType.digital_pdf
    )

    print("[seed] pipeline summary:")
    _summarize(factory, [digital.id, scanned.id, spreadsheet.id])

    # One draft report so the Review Queue also has a report to approve.
    with factory() as session:
        report = generate_report(session, "reserve_estimate", {"document_ids": [digital.id]})
        print(f"[seed] demo draft report #{report.id} created (reserve_estimate)")

    # One topic run so the Dashboard word cloud has data immediately.
    with factory() as session:
        run = run_topic_model(session, {"n_topics": 2})
        print(f"[seed] topic run #{run.id} created ({len(run.topics)} topics)")

    print("\n[seed] done. Try in the UI:")
    print("  - Chat:       'What is the coal reserve of Jharia as of 2019?'")
    print("  - Review:     resolve the coal_reserve 2019 conflict (1240 vs 1125)")
    print("  - Dashboard:  metrics + word cloud now have data")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())