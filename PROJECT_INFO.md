# CoalSutra — PROJECT_INFO

**CoalSutra** *(सूत्र — the thread)* — *every figure, traced to its source.*

Smart India Hackathon 2026 · **SIH26023** — **Ministry of Coal / Coal India Ltd. (CMPDI).**
This file is the exhaustive reference: what the project is, why it exists, every module/tool/script
implemented, what each one does, and the decisions behind them.

- **One-page summary + run guide** → [`README.md`](README.md)
- **Architecture-at-a-glance for AI agents** → [`CLAUDE.md`](CLAUDE.md)
- **Implementation record / memory** → [`PROJECT.md`](PROJECT.md)

---

## 1. What the project is

Coal India Ltd. (and its R&D arm CMPDI) keep geological and mining data scattered across decades
of documents — scanned PDFs, digital PDFs, images, spreadsheets, and historical archives —
that no single DB query can span. **CoalSutra** is an AI platform that turns that chaos into
structured, queryable, **traceable** data, and powers the three mandated SIH deliverables:

1. **Automated Report Generation** — extract structured data, validate it, and auto-fill
   report templates to `.pdf`.
2. **Word Cloud & Topic Identification** — explore topics/themes over the whole corpus.
3. **AI-Based Query & Response System** — grounded RAG with page-level source citations.

### The core promise
> *Every number on screen traces back to a source document + page/paragraph — and anything
> flagged during cross-source validation is gated by a human-in-the-loop review.*

This traceability (every fact carries `document_id` + `page_number` + `raw_snippet`) and the
review gate (conflicts are **never silently overwritten**) are the two hard requirements the
whole design is built around.

### Status
Production-grade prototype. The ingest → route → extract → normalize → validate → store backbone
runs end-to-end against SQLite/Postgres, with three consumer modules on top (query, reports,
topics), a metrics dashboard, a review queue, durable ingestion jobs, and two quality gates
(facts lint + golden RAG eval). Not yet deployed (no cloud accounts / CI — see Roadmap).

---

## 2. Milestones along the way

| # | Milestone | Where |
|---|-----------|-------|
| 1 | Ingest & classify documents (scanned vs digital vs image vs spreadsheet) | `services/ingestion/router.py` |
| 2 | Extract text/tables per page (3 extractors) | `services/ingestion/extractors/` |
| 3 | Normalize into one fact schema with mining-grammar rules | `services/normalization/normalizer.py` |
| 4 | Cross-source validation + human review queue | `services/normalization/validator.py`, `services/reviewing/` |
| 5 | RAG query with page citations | `services/rag/` (chunker→embedder→retriever→query_engine) |
| 6 | Report templates + strict-citation generator | `services/reporting/{templates,generator}.py` |
| 7 | Professional PDF export (cover, TOC, charts) | `services/reporting/exporter.py` |
| 8 | Word cloud + topic clusters | `services/topics/` |
| 9 | **Durable ingestion jobs** (retry/resume across restarts) | `models/job.py`, `services/ingestion/jobs.py` |
| 10 | **Facts-check lint** for report trustworthiness | `services/reporting/lint.py` |
| 11 | **Golden RAG evaluation harness** | `services/rag/eval.py`, `scripts/eval_rag.py` |
| 12 | **Real image OCR verification** (RapidOCR, slow-marked) | `tests/test_ocr_image.py` |
| 13 | Metrics dashboard + brand (CoalSutra) + dark/light theme | `routes/metrics.py`, frontend |

---

## 3. Architecture & data flow

```
                     ┌─────────────── CONSUMERS ───────────────┐
                     │                                          │
 upload ─► jobs ─► route ─► extract ─► normalize ─► validate ─► store ──► query (grounded RAG, page citations)
                                                                      ├─► reports (auto-generate → lint → PDF)
                                                                      └─► topics (word cloud / clusters)
                                                                              │
                                                              conflict_flags ─┘
                                                                    │
                                                              human review queue ─► resolved facts → reports → final
```

### Stage-by-stage
1. **Upload / Jobs** — `documents.py` saves the raw file, creates a `Document` row, enqueues an
   `IngestionJob` (persisted), and runs it via a FastAPI `BackgroundTask`. The job row — not the
   task — is the source of truth, so nothing is lost on restart. (`jobs.py` = claim → run →
   retry-with-backoff → give up; `resume_stale_jobs()` on app startup re-queues mid-flight work.)
2. **Route** — `ingestion/router.py` classifies each file (`scanned_pdf`, `digital_pdf`, `image`,
   `spreadsheet`) using extension + content heuristics (e.g. digital PDFs have a text layer;
   scans/images do not).
3. **Extract** — `ingestion/extractors/`:
   | Extractor | Handles | Technology |
   |-----------|---------|------------|
   | `native_pdf.py` | born-digital PDFs | pdfplumber (text + tables per page) |
   | `ocr.py` | scans / images | RapidOCR (default) · Tesseract · Hugging Face, auto-fallback |
   | `spreadsheet.py` | CSV / XLSX | pandas + openpyxl |
4. **Normalize** — `normalization/normalizer.py` flattens raw page text/tables into one fact
   schema: `entity, value, unit, date, source document, page`. Mining-grammar tuning:
   comma = thousands (`2,960` → 2960, never 2.960), month+year table rows → `date_reference`
   (`"March 1988"` → `1988-03-01`), a `PREFERRED_ENTITIES` catalog for stable labels, and a
   deterministic thousands/decimal repair safety net.
5. **Validate** — `normalization/validator.py`: rule-based checks + optional LLM cross-source
   comparison. Same entity + overlapping year + different value + different documents →
   `open` `ConflictFlag`. Conflicts are never silently overwritten.
6. **Store** — SQLAlchemy models / tables: `documents`, `document_pages`, `extracted_facts`,
   `document_chunks`, `conflict_flags`, `reports`, `topic_runs`, `ingestion_jobs`. Embeddings hang
   off chunks (pgvector-ready; `EMBEDDING_PROVIDER=hash` keeps a local-vector fallback).

---

## 4. Tech stack (exact versions)

| Layer | Choice | Version | Used for |
|-------|--------|---------|----------|
| Backend framework | FastAPI | 0.115.6 | REST API + OpenAPI docs |
| ASGI server | uvicorn[standard] | 0.34.0 | running the app |
| ORM | SQLAlchemy 2.x | 2.0.36 | models, session, querying |
| Migrations | Alembic | 1.14.1 | schema evolution (6 revisions) |
| Postgres driver | psycopg2-binary | 2.9.10 | connect to PG16 |
| Vector extension | pgvector | 0.3.6 | embedding storage/query |
| Config | pydantic-settings | 2.7.1 | `.env` → typed settings |
| Multiform uploads | python-multipart | 0.0.20 | file uploads |
| HTTP client (LLM) | httpx | 0.28.1 | calling OpenAI-compatible endpoints |
| Tests | pytest | 8.3.4 | hermetic offline test suite |
| PDF export | reportlab | 4.2.2 | professional PDFs + native vector charts |
| PDF parsing | pypdf / pdfplumber / pymupdf | 5.1.0 / 0.11.5 / 1.28.2 | digital PDF text+tables / rasterization |
| Spreadsheets | pandas / openpyxl | 2.2.3 / 3.1.5 | CSV/XLSX extraction |
| OCR | pytesseract / pdf2image | 0.3.13 / 1.17.0 | Tesseract path |
| OCR (default) | rapidocr_onnxruntime | 1.2.3 | pure-Pip ONNX OCR, offline |
| Faux-PDF fixture gen | fpdf2 | 2.8.2 | test digital PDFs |
| Frontend | Next.js 14 App Router | 14.2.15 | UI (server components by default) |
| Frontend deps | react / react-dom | 18.3.1 | UI runtime |
| Styling | Tailwind CSS | 3.4.14 | design system + dark mode |
| Types | TypeScript | 5.x | type safety |
| LLM (external) | Groq API (`openai/gpt-oss-120b`) | — | chat completion, RAG answer synthesis, extraction |
| Embeddings | `hash` provider (local) | — | deterministic local vectors (Groq has no embeddings) |
| Runtime | Docker Compose (db + backend + frontend) | — | containerized dev/run |

**Python note**: spec targets Python 3.12; the local dev venv actually runs **Python 3.14**,
which is why a couple of edge fixes were needed (see Known decisions — reportlab inline-color).

---

## 5. Repository layout (detail)

```
26023/
├── backend/
│   ├── app/
│   │   ├── api/routes/       health | documents | facts | query | reports | review | topics | metrics
│   │   ├── core/             config.py (pydantic-settings), database.py (engine/session/Base)
│   │   ├── models/           base, enums, document, document_page, fact, chunk, conflict,
│   │   │                     report, topic, job
│   │   ├── schemas/          pydantic request/response models (queries, reports, facts, ...)
│   │   ├── services/
│   │   │   ├── ingestion/    router.py, orchestrator.py, jobs.py, extractors/{native_pdf,ocr,spreadsheet}.py
│   │   │   ├── normalization/ normalizer.py, validator.py
│   │   │   ├── rag/          chunker.py, embedder.py, retriever.py, query_engine.py, eval.py
│   │   │   ├── reporting/    templates.py, generator.py, exporter.py, lint.py
│   │   │   ├── topics/       topic_model.py
│   │   │   ├── reviewing/    conflict + report decision logic
│   │   │   ├── pipeline.py   high-level ingest entry (legacy wrapper)
│   │   │   ├── normalizer.py, query_metrics.py
│   │   └── main.py           FastAPI app, CORS, routers, lifespan (startup resume)
│   ├── alembic/versions/     0001_pgvector → 0006_add_ingestion_jobs
│   ├── scripts/              seed_demo_data.py, eval_test_docs.py, eval_rag.py, lint_reports.py
│   ├── tests/                conftest.py + one test module per service/route
│   ├── Dockerfile, requirements.txt, pyproject.toml (pytest conf)
│   └── data/                 local SQLite dev DB (git-ignored)
├── frontend/
│   ├── app/                  layout.tsx, page.tsx, chat/, reports/, dashboard/, manage (ingest)/, review/
│   ├── components/           SidebarLayout, ThemeToggle, BrandLogo, SourceChip, SourceEvidencePanel
│   ├── Dockerfile, package.json, tailwind.config.ts, next.config.mjs
├── docker-compose.yml          db (pgvector/pgvector:pg16) + backend + frontend
├── .env.example                all config vars documented
├── README.md                   quick start
├── PROJECT.md / PROJECT_INFO.md / CLAUDE.md
```

---

## 6. Backend walkthrough — every module and what for

### `app/core/`
- **`config.py`** — `Settings(BaseSettings)` reads `.env` → attributes: `DATABASE_URL`,
  `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_TIMEOUT`, `EMBEDDING_PROVIDER`,
  `EMBEDDING_MODEL`, `EMBEDDING_DIM`, `OCR_PROVIDER`, `HUGGINGFACE_API_KEY`, `OCR_HF_MODEL`,
  `UPLOAD_DIR`, `API_V1_PREFIX`, `BACKEND_PORT`, `FRONTEND_PORT`.
- **`database.py`** — engine + `SessionLocal` + `Base` (the ORM base all models inherit). `get_db`
  yields a per-request session.

### `app/models/`
| Model | Table | Purpose |
|-------|-------|---------|
| `Document` | `documents` | one uploaded file; filename, `source_type`, `status`, `raw_file_path` |
| `DocumentPage` | `document_pages` | per-page extracted text/tables (`page_number`, `text`, `tables`) |
| `ExtractedFact` | `extracted_facts` | the normalized fact: `entity, value, unit, date_reference, page_number, raw_snippet, confidence` |
| `DocumentChunk` | `document_chunks` | chunked text + embedding vector (`pgvector`-ready) |
| `ConflictFlag` | `conflict_flags` | cross-source contradictions (`fact_a_id`, `fact_b_id`, `reason`, `status`, `resolution`, `resolved_by`) |
| `Report` | `reports` | generated report: `template`, `status` (draft/reviewed/final), `content` JSON, `export_path`, `review_note` |
| `TopicRun` | `topic_runs` | word-cloud / topic-cluster results (`terms` JSON) |
| `IngestionJob` | `ingestion_jobs` | durable upload jobs: status, attempts, max_attempts, last_error, next_attempt_at |
| `enums.py` | — | `SourceType`, `DocumentStatus`, `ConflictStatus`, `ReportStatus`, `JobStatus` |

### `app/services/`
- **`ingestion/router.py`** — `classify_document(path, content_type)` → `SourceType`. Heuristics:
  text-layer presence etc.
- **`ingestion/orchestrator.py`** — `ingest_document(document_id, session_factory)`:
  set `processing` → classify → extract pages → persist pages → normalize pages → persist facts →
  `flag_conflicts()` → chunk/embed (non-fatal on failure) → `processed`. Swallows its own errors
  (marks document `failed` + logs) so one bad file never crashes a batch.
- **`ingestion/jobs.py`** — durable queue: `enqueue_ingestion` (idempotent), `run_job`
  (claim → ingest → retry with exponential backoff `5s * 2^(attempts-1)` up to `max_attempts=3` →
  succeed/fail), `drain_queue` (run N due jobs), `resume_stale_jobs` (startup re-queue of
  mid-flight work + reset of docs stuck `processing`).
- **`ingestion/extractors/native_pdf.py`** — pdfplumber page-by-page text + tables.
- **`ingestion/extractors/ocr.py`** — page rasterize (PyMuPDF) + OCR via configured provider with
  runtime auto-fallback to RapidOCR; expensive CLIs spawned out-of-process, results merged row-wise.
- **`ingestion/extractors/spreadsheet.py`** — pandas read_csv/read_excel → row/column-structure
  aware pages.
- **`normalization/normalizer.py`** — `facts_from_pages(document_id, pages, provider)` → list of
  fact dicts. Rules: thousands comma, month→date, entity catalog, repair thousands/decimal; if an
  LLM is configured it buckets rows first, else rules alone.
- **`normalization/validator.py`** — `flag_conflicts()`: same entity + overlapping year + diff
  value + diff documents → open conflict. Self-consistent facts never circled as conflicts (both
  sides kept, reviewer decides).
- **`rag/chunker.py`** — split page text into overlapping chunks with context.
- **`rag/embedder.py`** — `embed_chunks` via `api` (OpenAI-compatible `/embeddings`) or `hash`
  (deterministic local vectors + cosine ground truth) and stores rows.
- **`rag/retriever.py`** — vector similarity top-k retrieval with a plausibility gate.
- **`rag/query_engine.py`** — retrieve → build prompt with evidence → LLM chat → cite
  `[page N]` per source chunk; emits `sources` for the evidence panel.
- **`rag/eval.py`** — **golden RAG evaluation**: 7 value questions + 1 non-answerable control,
  `score_retrieval` (recall of expected docs/values), `score_answer` (expected values/strings in
  RAG answer), `aggregate` for a CI-friendly summary.
- **`reporting/templates.py`** — 3 templates (`production_summary`, `coal_quality_report`,
  `reserve_estimate`), each with `executive_summary` + `observations` + `sources` sections and
  section-wise drafting instructions.
- **`reporting/generator.py`** — drafts each section from the in-scope fact set with **strict
  citation discipline** (must reference a supplied fact id, unseen ids dropped). Injects a senior
  analyst persona, entity hints, data coverage dates, style rules (~180-word cap). LLM down →
  fact-only bullet fallback. Persists `content.{sections,facts,scope}` on the Report.
- **`reporting/exporter.py`** — reportlab PDF: cover page, page-numbered TOC (two-pass build),
  numbered sections (1..n), Key Metrics table, deterministic Insight & Analysis with native bar
  charts, References. Footers with report id + page; keep-together headings. Handles the Py3.14
  inline-color gotcha via hex strings.
- **`reporting/lint.py`** — **facts-check linter**: walks report sections, extracts candidate
  numeric claims, verifies each against the DB fact set (value + unit tolerance), flags
  unmatched data-like figures (`error`) vs benign references like percentages/years/deltas
  (`info`). Matched-but-uncited figures are `error`; date masking keeps prose like "as of
  31-03-2026" noise-free.
- **`topics/topic_model.py`** — keyword frequency → word cloud data; doc-term matrix → cluster
  co-occurrence → labeled topic groups.
- **`reviewing/__init__.py`** — `resolve_conflict()` (A / B / both → resolved; neither →
  dismissed; state-guarded 409 on non-open) and `decide_report()` (approve → reviewed + note, or
  send_back stays draft).
- **`query_metrics.py`** — corpus metrics for landing/dashboard (counts, coverage, health).
- **`pipeline.py`** — thin legacy wrapper around `ingest_document`.

### `app/api/routes/` (thin; logic in services)
| Router | Endpoints |
|--------|-----------|
| `health` | GET `/health`, `/health/ready` |
| `documents` | POST `/upload` · GET `/` (list w/ fact_count) |
| `facts` | GET `/` (list, filters) |
| `query` | POST `/` (grounded answer + citations) |
| `reports` | GET `/templates` · GET `/` · POST `/generate` · GET `/{id}` · POST `/{id}/approve` · GET `/{id}/lint` · GET `/{id}/export` |
| `review` | GET `/queue` · POST `/conflicts/{id}/resolve` · POST `/reports/{id}/decide` |
| `topics` | POST `/` (word cloud + clusters) |
| `metrics` | GET `/` (dashboard metrics) |

---

## 7. Scripts (`backend/scripts/`)

| Script | What it does |
|--------|--------------|
| `seed_demo_data.py` | Generates 3 synthetic documents (digital PDF, scan-with-text-layer PDF, CSV) with deliberate cross-source conflict, runs them through the real pipeline, and creates a draft report so every screen has data. `--reset` wipes first. |
| `eval_test_docs.py` | Ingests fixtures in `Test_docs/` (Barkhola reserve report, scanned geological survey, production scan) and prints an extraction report (attached dates, reconciled sums, stable labels). |
| `eval_rag.py` | Golden RAG eval runner: `--offline` (pure scoring over ingested corpus, CI-safe) or online (LLM answers with 429-retry + utf-8-safe stdout; `os._exit(0)` to dodge RapidOCR thread-pool hangs). |
| `lint_reports.py` | Lints every drafted report in the DB; prints findings, exits 1 on `error`-level issues (CI hook). |

---

## 8. Frontend (Next.js 14 App Router, TypeScript, Tailwind)

| Route | Purpose |
|-------|---------|
| `/` | Landing / overview with live corpus metrics + offline state |
| `/chat` | Grounded RAG answers with `SourceChip` citations + `SourceEvidencePanel` |
| `/reports` | List drafts → generate → **approve** → **export PDF** (downloads report) |
| `/dashboard` | Word cloud, topic clusters, document health |
| `/ingest` | Drag-and-drop upload, pipeline status polling |
| `/review` | Human-in-the-loop conflict resolution queue |

Components: `SidebarLayout` (rail + mobile drawer), `ThemeToggle`, `BrandLogo` (SVG mark),
`SourceChip`, `SourceEvidencePanel`. Favicon `app/icon.svg`.

Design system:
- **Brand** — coal strata threaded by an amber *sutra* thread rising into a knowledge spark.
- **Dark/light theme** — class-based Tailwind, persisted in `localStorage` (`cmpdi-theme`),
  pre-hydration script prevents flash, OS default respected.
- Apple system font stack; semantic SVG icons (no emoji), theme-aware fills.

---

## 9. Tests — what's covered & how

Suite: **109 passing + 2 slow deselected** (default `-m "not slow"`), fully **offline**
(`tests/conftest.py` forces `LLM_API_KEY=""`, `EMBEDDING_PROVIDER=hash`).

| Test module | Covers |
|-------------|--------|
| `test_ingest.py` | orchestrator state transitions, extractor output shapes, digital-PDF routing |
| `test_normalization_validator.py` | thousands/comma rules, month→date, conflicts creation |
| `test_ingestion_jobs.py` | enqueue idempotency, retry→backoff→give-up, drain-only-due, startup resume |
| `test_rag.py`, `test_rag_eval.py` | chunker/embedder/retriever/query engine + golden eval scoring |
| `test_reporting.py` | template variety, strict-citation, PDF export structure |
| `test_report_lint.py` | linter error/info classification over crafted sections |
| `test_topics.py` | word cloud + clusters over ingested docs |
| `test_review.py` | conflict resolution state machine + report approval gate |
| `test_facts_api.py`, `test_health.py`, `test_metrics.py`, `test_upload_endpoint.py` | API lifecycle |
| `test_ocr_image.py` (`-m slow`) | **real RapidOCR** over a generated image-only document (~60s) |
| `test_modelling.py` | model/table mappings |

---

## 10. Tools used — and what each is for

**Vendored/CLI tooling on the dev machine**
- **Python 3.14** venv at `backend/.venv` — everything runs through `& .\.venv\Scripts\python.exe`.
- **gh 2.98.0** — GitHub CLI (repo `5at4am/CoalSutra`, pushed via commits).
- **git 2.55.0** — version control, `origin/main`.
- **No Docker / no Ollama on the machine** — Docker Compose config is written and ready but
  untested locally; PG-related tests use SQLite in-memory; embedding fallback is `hash`.

**External services (behind env/config, never committed)**
- **Groq API** — `LLM_BASE_URL=https://api.groq.com/openai/v1`, `LLM_MODEL=openai/gpt-oss-120b`:
  used for LLM-first fact extraction, RAG answer synthesis, and report drafting. Free-tier
  rate-limits (HTTP 429) are handled with retry in scripts.
- **Hugging Face Inference API** — optional `huggingface` OCR provider (`microsoft/trocr-base-printed`);
  unreachable from typical dev machines → runtime auto-fallback to RapidOCR.
- **RapidOCR (ONNX)** — default OCR: pure-pip, offline, no system binaries.

**What each piece is used for (quick map)**
- reportlab → PDF export; pdfplumber → digital PDFs; PyMuPDF → rasterize scans;
  rapidocr/tesseract → OCR; pandas/openpyxl → spreadsheets; httpx → LLM calls;
  pydantic-settings → env config; alembic → migrations; pytest → quality;
  FastAPI/uvicorn → API; SQLAlchemy → ORM; Next.js/Tailwind → UI.

---

## 11. Environment variables (`.env.example` → `.env`)

| Var | Meaning | Default |
|-----|---------|---------|
| `DATABASE_URL` | SQLAlchemy connection string | `postgresql+psycopg2://cmpdi:cmpdi@localhost:5432/cmpdi` |
| `LLM_API_KEY` | LLM key (empty = rule-based fallback) | `replace-me` |
| `LLM_MODEL` | model id | `gpt-4o-mini` (Groq: `openai/gpt-oss-120b`) |
| `LLM_BASE_URL` | OpenAI-compatible endpoint | `https://api.openai.com/v1` |
| `LLM_TIMEOUT` | LLM request timeout | `60` |
| `EMBEDDING_PROVIDER` | `api` or `hash` | `api` (repo ships `hash` for Groq) |
| `EMBEDDING_MODEL` / `EMBEDDING_DIM` | embeddings model + dimension | `text-embedding-3-small` / `1536` |
| `OCR_PROVIDER` | `tesseract` / `rapidocr` / `huggingface` | `tesseract` (dev uses `rapidocr`) |
| `HUGGINGFACE_API_KEY` / `OCR_HF_MODEL` | HF OCR provider | empty / `microsoft/trocr-base-printed` |
| `UPLOAD_DIR` | where raw uploads + exported PDFs live | `./uploads` |
| `BACKEND_PORT` / `FRONTEND_PORT` | port overrides | `8000` / `3000` |

---

## 12. Run it

```bash
# containerized (db + backend:8000 + frontend:3000)
docker compose up --build

# local backend (SQLite works; use backend/.venv)
cd backend && uvicorn app.main:app --reload

# local frontend
cd frontend && npm run dev

# tests / evals
cd backend
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m pytest -m slow
.venv\Scripts\python.exe scripts\eval_rag.py --offline
.venv\Scripts\python.exe scripts\seed_demo_data.py --reset

# migrate
cd backend && alembic upgrade head
```

---

## 13. Known decisions & limitations

- **Hash embeddings** — Groq has no embeddings endpoint, so `EMBEDDING_PROVIDER=hash` gives
  deterministic local vectors; pgvector is wired and ready behind real Postgres.
- **One honest eval finding** — with hash embeddings the non-answerable control still retrieves
  junk chunks (weak vector gate); the golden eval reports it rather than hiding it.
- **In-process "queue"** — uploads execute in a `BackgroundTask`; the durable `ingestion_jobs`
  table makes this restart-safe, but it is not a distributed queue.
- **LLM nondeterminism** — mitigated by deterministic rule fallback + snippet repair; the RAG
  eval + fact lint are the gates, not single-shot LLM outputs.
- **No auth yet** — `resolved_by` is a free-text field so far; a passcode session is on the roadmap.
- **reportlab on Python 3.14** — inline `<font color='Color(...)'>` crashes; pass hex strings.
- **Next.js Windows build flakiness** — orphan `.next`/node servers; `next dev` is the stable path.
- **Voice of the field data** — eval corpus `%TEMP%\testdocs_eval.db` is a fixed snapshot;
  production_table_scan.png + 2 ChatGPT-created images currently extract 0 facts (gap, known).

---

## 14. Roadmap

1. ✅ Ingest/route/extract/normalize/validate/store + query + reports + topics + metrics + review
2. ✅ Professional report PDFs + stronger generation prompts
3. ✅ Facts-check lint + golden RAG eval + real-OCR test
4. ✅ Durable ingestion jobs (retry/resume)
5. ⬜ CI — GitHub Actions (pytest → RAG eval --offline → report lint)
6. ⬜ Review passcode auth so `resolved_by` is real identity
7. ⬜ Frontend polish: report-body preview, inline-SVG KPI trend charts, Hindi toggle
8. ⬜ Deploy: `render.yaml`, `vercel.json`/Netlify, deploy workflow, Neon Postgres, docs + screenshots