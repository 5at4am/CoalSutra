"""Evaluate the grounded RAG engine against a golden set over Test_docs.

Usage (from backend/):
    python scripts/eval_rag.py            # ingestion + retrieval + LLM answers
    python scripts/eval_rag.py --offline  # ingestion + retrieval only (CI-safe)

Prints per-case and aggregate metrics (retrieval recall, answer precision,
citation validity, refusal rate).
"""
import argparse
import os
import sys
import tempfile


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    outfile = sys.stdout
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="re-ingest Test_docs into a throwaway DB instead of reusing one",
    )
    args = parser.parse_args()

    tmp_db = os.path.join(tempfile.gettempdir(), "testdocs_eval.db")
    if args.fresh and os.path.exists(tmp_db):
        os.remove(tmp_db)
    os.environ["DATABASE_URL"] = "sqlite:///" + tmp_db
    os.environ.setdefault("EMBEDDING_PROVIDER", "hash")

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from app.core.database import Base, SessionLocal, engine
    from app.core.llm import embed_text
    from app.models import Document
    from app.models.enums import DocumentStatus, SourceType
    from app.services.ingestion.orchestrator import ingest_document
    from app.services.rag import retriever
    from app.services.rag.eval import GOLDEN_CASES, aggregate, score_answer, score_retrieval
    from app.services.rag.query_engine import answer_question

    def seed_corpus() -> set[str]:
        session = SessionLocal()
        names: set[str] = set()
        files = [
            "Barkhola_Coal_Block_Reserve_Estimation_Summary_2026.pdf",
            "geological_survey_report_scan.pdf",
            "production_table_scan.png",
            "ChatGPT Image Sep 18, 2026, 03_48_07 PM.png",
            "ChatGPT Image Sep 18, 2026, 03_49_28 PM.png",
        ]
        base_dir = r"C:\Users\PC\Desktop\SIH\26023\Test_docs"
        for name in files:
            path = os.path.join(base_dir, name)
            if not os.path.exists(path):
                continue
            if session.query(Document).filter_by(filename=name).first():
                names.add(name)
                continue
            print(f"[seed] ingesting {name}", flush=True)
            doc = Document(
                filename=name,
                source_type=SourceType.digital_pdf,
                status=DocumentStatus.pending,
                raw_file_path=path,
            )
            session.add(doc)
            session.commit()
            try:
                ingest_document(doc.id, session_factory=SessionLocal)
            except Exception as exc:  # noqa: BLE001 - keep evaluating the rest
                print(f"[seed] ingest FAILED {name}: {exc}")
            names.add(name)
            session.expire_all()
        session.close()
        return set(names)

    Base.metadata.create_all(engine)
    names = seed_corpus()
    session = SessionLocal()

    retrieval_rows: list[dict] = []
    answer_rows: list[dict] = []
    for case in GOLDEN_CASES:
        if args.offline:
            query_embedding = embed_text(case["question"])
            if (
                retriever.best_vector_similarity(session, query_embedding)
                < 0.2
            ):
                chunks = []
            else:
                chunks = retriever.retrieve(
                    session, case["question"], query_embedding, top_k=5
                )
            answer = ""
        else:
            result = _answer_with_retry(session, case["question"])
            answer = result["answer"]
            chunks = [
                {"document_name": c["document_name"], "text": c["snippet"]}
                for c in result.get("citations", [])
            ]
        r = score_retrieval(case, chunks)
        retrieval_rows.append({**{"id": case["id"]}, **r})
        if not args.offline:
            a = score_answer(case, answer, result["citations"], names)
            answer_rows.append({**{"id": case["id"]}, **a})
        print(
            f"[{case['id']:<24}] recall={r['retrieval_recall']} "
            f"docs={r['docs_in_retrieved']} values={r['values_in_retrieved']} "
            f"| {answer[:60]}"
        )
        outfile.flush()

    session.close()
    print("\n=== RETRIEVAL (aggregate) ===")
    print(aggregate(retrieval_rows))
    if answer_rows:
        print("\n=== ANSWER (aggregate) ===")
        print(aggregate(answer_rows))
    outfile.flush()
    os._exit(0)


def _answer_with_retry(session, question: str, tries: int = 3) -> dict:
    """Call the query engine, retrying on provider rate-limits (429)."""
    import time

    degraded = "could not generate an answer"
    for attempt in range(tries):
        result = answer_question(session, question)
        if degraded not in result["answer"]:
            return result
        if attempt + 1 < tries:
            time.sleep(3 * (attempt + 1))
    return result


if __name__ == "__main__":
    main()