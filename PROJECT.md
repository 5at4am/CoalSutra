# CoalSutra — Project Memory & Implementation Record

**CoalSutra** *(सूत्र — the thread)* — *every figure, traced to its source.*

Smart India Hackathon 2026 · **SIH26023** — Ministry of Coal / Coal India Ltd. (CMPDI).
CoalSutra turns CMPDI/CIL subsidiaries' scattered geological & mining documents — scanned
PDFs, digital PDFs, images, spreadsheets, historical archives — into structured, queryable,
**traceable** data, and powers three mandated deliverables:

1. **Automated Report Generation** — extraction + validation + template-driven auto-fill.
2. **Word Cloud & Topic Identification** — corpus-level topic/theme exploration.
3. **AI-Based Query & Response** — grounded RAG with page-level source citations.

The core promise: *every number on screen traces back to a source document + page/paragraph,
and anything flagged during cross-source validation is gated by a human-in-the-loop review.*

---

## Tech Stack

| Layer            | Choice                                                        |
|------------------|---------------------------------------------------------------|
| Backend          | FastAPI (Python 3.12 spec; dev venv runs Python 3.14) + uvicorn |
| ORM / migrations | SQLAlchemy 2.x + Alembic (5 revisions)                         |
| Postgres         | `pgvector/pgvector:pg16` (PG16 + `vector` extension, migration 0001) |
| Frontend         | Next.js 14 App Router, TypeScript, Tailwind CSS                |
| PDF export       | reportlab 4.2.2 (native vector charts, no extra deps)          |
| OCR (runtime)    | RapidOCR (default) / Tesseract / Hugging Face — choose via `OCR_PROVIDER`, auto-fallback |
| LLM (runtime)    | generic OpenAI-compatible provider behind `LLM_API_KEY` (ships on Groq) |
| Embeddings       | `api` provider or local `hash` fallback (`EMBEDDING_PROVIDER`) |

---

## Architecture & Flow

```
                    ┌─────────────── CONSUMERS ───────────────┐
                    │                                          │
 upload ─► route ─► extract ─► normalize ─► validate ─► store──┼──► query (grounded RAG, page citations)
                                                            │  ├──► reports (auto-generate + PDF export)
                                                            │  └──► topics (word cloud / cluster)
                                                            ▼
                                              conflict_flags ─┘
                                                    │
                                              human review queue ──► resolved facts → reports → final
```

### Stage-by-stage flow

1. **Ingest / Route** — `backend/app/services/ingestion/router.py` classifies each uploaded
   file as `scanned_pdf`, `born-digital pdf`, `image` or `spreadsheet` (extension + content
   heuristics). `orchestrator.py` routes to the right extractor.
2. **Extract** — `backend/app/services/ingestion/extractors/`:
   | Extractor        | Handles                                  |
   |------------------|------------------------------------------|
   | `native_pdf.py`  | born-digital PDFs (pdfplumber-style text/tables) |
   | `ocr.py`         | scans / images — `tesseract` / `rapidocr` / `huggingface`, runtime auto-fallback to RapidOCR |
   | `spreadsheet.py` | CSVs / XLSX row/column normalization      |
3. **Normalize** — `backend/app/services/normalization/normalizer.py` flattens raw page
   text/tables into the single fact schema: `entity, value, unit, date, source document,
   page`. CMPDI/coal-geology tuning:
   - comma = thousands separator (`2,960` = 2960, **never** 2.960),
   - month+year table rows → `date_reference` ("March 1988" → `1988-03-01`),
   - `PREFERRED_ENTITIES` catalog keeps labels stable across runs,
   - `_repair_thousands_decimal` is a deterministic safety net re-reading the snippet.
4. **Validate** — `backend/app/services/normalization/validator.py` runs rule-based checks +
   LLM cross-source comparison; **conflicts are flagged for human review, never silently
   overwritten** (see HITL below).
5. **Store** — SQLAlchemy models (`backend/app/models/`): `document`, `document_page`,
   `fact`, `chunk`, `conflict`, `report`, `topic`. Chunks/embeddings ready for pgvector;
   `EMBEDDING_PROVIDER=hash` keeps it fully runnable without an embeddings API.

---

## Human-in-the-loop (HITL)

Two review gates, both surfaced in the **Review Queue** (`backend/app/api/routes/review.py`,
UI `frontend/app/review/page.tsx`):

**Gate A — Conflict review (facts).**
- Detection: `backend/app/services/normalization/validator.py` `flag_conflicts()` — pure
  rule: same `entity` + overlapping year + **different value** + **different documents** →
  `open` `ConflictFlag`. Called at the end of every ingest
  (`backend/app/services/ingestion/orchestrator.py`).
- Storage: `conflict_flags` table (`backend/app/models/conflict.py`): `fact_a_id`,
  `fact_b_id`, `reason`, `status`, `resolution`, `resolved_by`.
- Resolution logic: `backend/app/services/reviewing/__init__.py` `resolve_conflict()` — A /
  B / both → `resolved`, neither → `dismissed`; state-guarded (409 on non-open flags).
- Both facts shown side-by-side with document, page, snippet, confidence.

**Gate B — Report approval gate.** Reports are generated as `draft`; `decide_report()`
(`reviewing/__init__.py`) advances `approve` → `reviewed` (+ `review_note`) or `send_back`
(+ note, stays draft). API `/api/v1/reports/{id}/approve` steps draft → reviewed → final.

---

## Documents — storage & processing

- Upload: `backend/app/api/routes/documents.py` — raw file written to
  `settings.UPLOAD_DIR` (default `./uploads`; `backend/.env` sets `UPLOAD_DIR=./uploads`,
  so from the backend working dir files land in **`backend/uploads/`**) under a sanitized
  `{uuid4().hex}{suffix}` name. Original filename kept on the `Document` row.
- Provenance: each fact carries `document_id` + `page_number` + `raw_snippet`; the
  `Document.raw_file_path` column is the storage handle the whole pipeline reads.
- Ingestion runs as a FastAPI `BackgroundTask` → `ingest_document(document.id)`.
  *(Prototype note: in-process task, not a queue — a restart mid-ingest leaves a doc
  `pending`.)*
- Report PDFs export to `{UPLOAD_DIR}/reports/report_{id}.pdf` (`exporter.py`).

---

## Report PDF (deliverable quality)

Generated by `backend/app/services/reporting/`:

- `templates.py` — 3 templates (`production_summary`, `coal_quality_report`,
  `reserve_estimate`); each leads with an `executive_summary`, has an
  `observations` section for management commentary, and closes with an automatic
  `sources` section. Per-section drafting instructions are craft-tuned.
- `generator.py` — drafts each section from a bounded, validated fact set with
  STRICT citation discipline (every figure must reference a supplied fact id;
  unseen ids are dropped). Prompt injects a senior-analyst role, entity hints,
  data coverage dates, and explicit style rules (no bullet openings, cite on
  introduction, quantify moves only between dated facts, say when data is
  insufficient, ~180-word cap). Persists `content.sections`, `content.facts`
  and `content.scope` on the `Report` row. LLM down → fact-only bullet fallback.
- `exporter.py` — renders a structured, professional PDF (reportlab, no new deps;
  two-pass build for correct page numbers):
  1. **Cover page** — centred CoalSutra brand, title, and a meta grid
     (template / color-coded status / generated / entities / period / facts /
     sources).
  2. **Contents** — numbered sections with real page numbers (TableOfContents).
  3. **1. Executive Summary** — the template's drafted summary.
  4. **2. Key Metrics** — auto table of every in-scope fact: entity / value /
     unit / date / source / page / confidence, zebra-striped, capped at 40 rows.
  5. **3. Insight & Analysis** — computed DETERMINISTICALLY from facts (never
     invented): first→latest value, absolute + % change, trend, min/max, and the
     largest single-period move; native vector **bar charts** (gridlined, dated)
     for each numeric series with ≥ 2 points (up to 2 charts).
  6. **4..n narrative sections** — LLM prose, still cited; numbered.
  7. **last. References / Sources** — every cited document + page.
  - Page furniture: amber brand header strip + title, footer with report id and
    page number; headings keep-together with their lead paragraph.
- Route: `GET /api/v1/reports/{id}/export` returns the PDF inline and records
  `export_path` on the row (frontend "Export PDF" in `frontend/app/reports/page.tsx`).

---

## API surface (all under `/api/v1`, FastAPI)

| Router            | Endpoints                                                        |
|-------------------|------------------------------------------------------------------|
| `health`          | GET `/health`, `/health/ready`                                   |
| `documents`       | POST `/upload`, GET `/` (list/poll, DocumentSummary)             |
| `facts`           | GET `/` (list, filters)                                          |
| `query`           | POST `/` (grounded answer + page-level citations)                |
| `reports`         | GET `/templates` · GET `/` · POST `/generate` · GET `/{id}` · POST `/{id}/approve` · GET `/{id}/export` |
| `review`          | GET `/queue` · POST `/conflicts/{id}/resolve` · POST `/reports/{id}/decide` |
| `topics`          | POST `/` (word cloud + topic clusters)                            |
| `metrics`         | GET `/` (corpus metrics for landing/dashboard)                    |

All handlers are thin; business logic lives in `app/services/`. Responses via Pydantic
schemas in `app/schemas/`.

---

## Frontend (Next.js 14 App Router, TypeScript, Tailwind)

| Route        | Purpose                                                        |
|--------------|----------------------------------------------------------------|
| `/`          | Landing / overview with live corpus metrics + offline state    |
| `/chat`      | Ground-RAG answers with SourceChip citations + evidence panel  |
| `/reports`   | Draft + approve + export reports (downloads the PDF)           |
| `/dashboard` | Word cloud, topic clusters, document health                    |
| `/ingest`    | Drag-and-drop upload, pipeline status polling                  |
| `/review`    | Human-in-the-loop conflict resolution queue                    |

Components — `components/`: `SidebarLayout` (fixed desktop rail + mobile drawer),
`ThemeToggle`, `BrandLogo` (SVG mark), `SourceChip`, `SourceEvidencePanel`.
Favicon: `app/icon.svg`.

Design system:
- **Brand** — **CoalSutra** mark: coal strata threaded by an amber *sutra* thread rising
  into a knowledge spark; applied to sidebar, metadata title, landing footer, favicon.
- **Dark / light theme** — class-based Tailwind `darkMode`; persisted in `localStorage`
  (`cmpdi-theme`); pre-hydration inline script in `layout.tsx` prevents flash; OS default
  respected. Verified end-to-end (class flips + body bg both states + reload persistence).
- **Apple system font stack** — `-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, …`.
- Semantic SVG icons inline (no emoji) — theme-aware via Tailwind `fill-*`/`stroke-*`.

---

## Everything implemented (recent work log)

1. **Full ingestion pipeline** — router + orchestrator + 3 extractors + normalizer +
   validator + chunker/embedder/retriever/query engine + topics + review services.
2. **Report & PDF system** — 3 templates, strict-citation generation, fact + scope
   persistence, and the professional PDF export (cover / Key Metrics / Insight &
   Analysis with charts / references). Verified: 5-page smoke PDF, all blocks + bar-chart
   vectors present.
3. **Human-in-the-loop** — conflict flags auto-created, review queue + resolution API +
   `/review` UI, report approval gate.
4. **Brand rename** — **CoalSutra** across UI (logo `BrandLogo.tsx`, favicon `icon.svg`,
   sidebar, landing footer, metadata), docs (`README.md`, `CLAUDE.md`, this file),
   backend `PROJECT_NAME` (`app/core/config.py`), `frontend/package.json` name. Old
   `NavBar.tsx` removed.
5. **Dark/light theme** across all six pages + shared components; **left sidebar**
   navigation.
6. **OCR provider chain** `tesseract | rapidocr | huggingface` with runtime auto-fallback;
   `ocr.py` row-reconstruction bugs fixed.
7. **Normalizer hardening** — comma/thousands rule, month→date, `PREFERRED_ENTITIES`
   catalog, thousands-decimal repair, deterministic labels.
8. **Real-document eval harness** — `backend/scripts/eval_test_docs.py` runs over
   `Test_docs/` (Barkhola report, scanned geological survey, production scan): attached
   dates, reconciled seam sums, stable labels. `seed_demo_data.py` seeds every screen.
9. **Report content + PDF upgrades** — richer templates (executive summary +
   observations per template), stronger drafting prompts (role, coverage, style
   rules, trend quantification), and a restructured PDF (cover page, page-numbered
   table of contents, numbered sections, keep-together headings, gridlined charts,
   biggest single-period move highlight).
10. **Tests** — `pytest` green: **88 passing** (hermetic: forced no-LLM + hash
   embeddings), covering pipelines, API lifecycle, review, topics, RAG, metrics,
   normalizer, modelling, uploads.

---

## Run it

```bash
docker compose up --build                       # db + backend :8000 + frontend :3000
# or locally:
cd backend  && uvicorn app.main:app --reload    # backend/.venv recommended
cd frontend && npm run dev
```

Tests / evals (use the backend venv):
```bash
cd backend && .venv\Scripts\python.exe -m pytest
cd backend && .venv\Scripts\python.exe scripts\eval_test_docs.py
cd backend && .venv\Scripts\python.exe scripts\seed_demo_data.py
```

Config: `.env.example` → `.env`. Key vars — `DATABASE_URL`, `LLM_API_KEY`,
`LLM_BASE_URL`/`LLM_MODEL` (ships on Groq), `EMBEDDING_PROVIDER` (`api`|`hash`),
`OCR_PROVIDER` (`tesseract`|`rapidocr`|`huggingface`), `HUGGINGFACE_API_KEY`/`OCR_HF_MODEL`,
`UPLOAD_DIR` (default `./uploads`). **Never commit `.env`.**

---

## Known limitations & decisions

- **Hugging Face Inference** is unreachable from typical dev machines
  (Router `model_not_supported` for free-tier vision models) → OCR defaults to
  **RapidOCR**, which works fully offline; HF stays the plug-in for deployed envs.
- **Groq embeddings**: no endpoint → local `hash` embeddings fallback keeps everything
  runnable; pgvector is wired and ready behind a real Postgres (`docker compose up`).
- **In-process ingestion** — `BackgroundTask`, not a queue (prototype depth).
- **Groq zero-shot nondeterminism** — mitigated by rule-fallback + snippet repair; a
  deterministic eval is the gate, not single-shot LLM output.
- **Next.js build flakiness on Windows** — intermittent incomplete `.next` (missing
  chunk / BUILD_ID) + orphan `node` servers squatting port 3000. Guarded by
  `%TEMP%\opencode\rebuild.ps1` (clean-build retry + BUILD_ID + all-assets-200
  validation); `next dev` is the stable day-to-day path.
- **reportlab on Python 3.14** — avoid inline `<font color='Color(...)'>` objects; pass
  hex strings so the (ast.Str-dependent) inline color parser is never hit.