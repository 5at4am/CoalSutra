# CoalSutra — CMPDI Reporting Assistant

**CoalSutra** — *every figure, traced to its source.*

AI platform for the **Smart India Hackathon 2026 · SIH26023** — Ministry of Coal / Coal India Limited.
Ingests CMPDI/CIL subsidiaries' geological & mining documents (scanned PDFs, digital PDFs, images,
spreadsheets), extracts structured data with page-level citations, answers natural-language
questions (RAG), auto-generates reports, and surfaces topic/word-cloud analytics.

**Status: prototype.** The full ingest → route → extract → normalize → validate → store
pipeline runs end-to-end, with RAG query (cited answers), report generation + PDF export,
facts-check linting, a golden RAG evaluation harness, word-cloud/topic analytics, a metrics
dashboard, and a human-in-the-loop review queue for cross-source conflicts. Uploads are
processed through **durable ingestion jobs** that survive restarts and retry with backoff.
LLM/OCR providers plug in behind `LLM_API_KEY` / `OCR_PROVIDER`; without a key the pipeline
degrades gracefully (rule-based extraction, fact-only cited report bodies). Run the demo
seeder (`Seed demo data` below) to populate everything with synthetic, non-CIL data.

See [`PROJECT_INFO.md`](PROJECT_INFO.md) for an exhaustive breakdown: every module, tool, script,
test, and the decisions behind each piece.

## Stack
- **Backend**: Python 3.12 (dev venv runs 3.14), FastAPI, SQLAlchemy 2 + Alembic, pytest
- **Frontend**: Next.js 14 (App Router), TypeScript, Tailwind CSS
- **DB**: PostgreSQL 16 + pgvector (embeddings ready; SQLite works for dev/tests)
- **PDF export**: reportlab 4.2.2 (native vector charts, no extra deps)
- **OCR**: RapidOCR / Tesseract / Hugging Face (auto-fallback)
- **LLM**: generic OpenAI-compatible provider behind `LLM_API_KEY` (ships configured for Groq)

## Folder Structure
```
├── backend/        FastAPI app (app/api, app/core, app/models, app/schemas, app/services)
│   ├── alembic/    6 migrations (pgvector → review columns → ingestion_jobs)
│   ├── scripts/    seed_demo_data, eval_test_docs, eval_rag, lint_reports
│   └── tests/      pytest suite (109 passing + 2 slow OCR tests by default)
├── frontend/       Next.js app (/chat, /reports, /dashboard, /review, /ingest)
├── docker-compose.yml
├── .env.example
├── CLAUDE.md       architecture-at-a-glance for AI agents
├── PROJECT.md      implementation record / project memory
├── PROJECT_INFO.md exhaustive project documentation
└── README.md
```

For the full pipeline (ingest → route → extract → normalize → validate → store → query/report/topics),
see `CLAUDE.md`.

## Prerequisites
- Docker Desktop (or Docker + Compose plugin)
- Node.js 20+ (for frontend dev outside Docker)

## Quick Start (Docker)

```bash
cp .env.example .env        # adjust secrets if you like
docker compose up --build
```

| Service  | URL                          |
|----------|------------------------------|
| Frontend | http://localhost:3000        |
| Backend  | http://localhost:8000        |
| API docs | http://localhost:8000/docs   |
| Health   | http://localhost:8000/api/v1/health |
| Postgres | localhost:5432 (cmpdi/cmpdi) |

Verify:
```bash
curl http://localhost:8000/api/v1/health
# {"status":"ok","database":"connected"}
```

## Local Development Without Docker

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# point DATABASE_URL at a local Postgres, e.g.:
#   postgresql+psycopg2://cmpdi:cmpdi@localhost:5432/cmpdi

uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
```

## Seed demo data

Generate three synthetic documents (born-digital PDF, scanned-quality PDF with a baked-in
text layer, and a spreadsheet CSV) and run them through the real pipeline — extraction,
embeddings, conflict detection, and a draft report — so every screen has data. All content is
clearly fabricated placeholder data, and one deliberate cross-source conflict (coal reserve
2019: 1240 MT vs 1125 MT) lands in the Review Queue so you can exercise resolution.

```bash
cd backend
python scripts/seed_demo_data.py                                   # uses DATABASE_URL
python scripts/seed_demo_data.py --url sqlite:///data/seed_demo/demo.db
python scripts/seed_demo_data.py --reset                           # wipe tables, seed fresh
```

Requires a migrated Postgres (`alembic upgrade head`) for `DATABASE_URL` deployments; the
script also creates missing tables idempotently. The scanned-quality PDF ships with its OCR
text layer baked in so it ingests without a tesseract/poppler binary; after ingestion its
`source_type` is rewritten to `scanned_pdf`. Drop a real image-only scan there instead to
exercise true OCR via `OCR_PROVIDER`.

## Tests
```bash
cd backend
.venv\Scripts\python.exe -m pytest          # 109 passing (SQLite, hermetic)
.venv\Scripts\python.exe -m pytest -m slow  # +2 real RapidOCR image tests (~60s)
```

The suite forces `LLM_API_KEY=""` and `EMBEDDING_PROVIDER=hash` (see `tests/conftest.py`) so it is
fully offline and deterministic. The two slow OCR tests run real RapidOCR on a generated
image-only document and are excluded from the default run via `-m "not slow"`.

### Quality gates / evals
- **RAG golden eval** — `scripts/eval_rag.py` runs 7 value questions + 1 non-answerable control
  against a known corpus and scores retrieval recall + answer correctness (offline-safe with
  `--offline`; online mode uses the configured LLM with retry on rate limits).
- **Report facts lint** — `scripts/lint_reports.py` checks every drafted report for unverifiable
  figures, matched-but-uncited numbers, or unsupported claims; exits non-zero on `error`-level
  findings. The same checks run via `GET /api/v1/reports/{id}/lint`.

## Migrations
```bash
cd backend
alembic upgrade head        # 0001 pgvector → 0006 ingestion_jobs
alembic revision --autogenerate -m "message"   # after adding SQLAlchemy models
```

## Env Vars
See `.env.example` for all variables:

- `DATABASE_URL` — SQLAlchemy connection string (defaults to the `db` compose service)
- `LLM_API_KEY` — provider-agnostic key for the LLM (RAG/extraction/report generation)
- `LLM_BASE_URL` / `LLM_MODEL` — OpenAI-compatible endpoint + model id. Point any
  compatible gateway here; the repo ships configured for **Groq** (`https://api.groq.com/openai/v1`,
  e.g. `LLM_MODEL=openai/gpt-oss-120b`).
- `EMBEDDING_PROVIDER` — `api` (OpenAI-compatible `/embeddings`, default) | `hash`
  (local vectors). Use `hash` when the chat provider has no embeddings endpoint — Groq does not,
  so the shipped `.env` uses `hash`. Dimension stays `EMBEDDING_DIM`.
- `OCR_PROVIDER` — `tesseract` (default, needs tesseract binary + poppler; both in the
  Docker image) | `rapidocr` (pure-pip ONNX OCR, works on any machine incl. Windows dev
  boxes) | `huggingface` (hosted image-to-text via the HF Inference API —
  set `HUGGINGFACE_API_KEY`/`OCR_HF_MODEL`). If the configured provider is unusable at
  runtime the pipeline auto-falls back to `rapidocr`.
- `HUGGINGFACE_API_KEY` / `OCR_HF_MODEL` — Hugging Face token + image-to-text model for the
  `huggingface` OCR provider (e.g. `microsoft/trocr-base-printed`).
- `UPLOAD_DIR` — where uploaded raw files are saved
- `BACKEND_PORT` / `FRONTEND_PORT` — optional port overrides

### Groq (shipped default)
`backend/.env` and the root `.env` are pre-filled with a Groq key, `LLM_BASE_URL=https://api.groq.com/openai/v1`,
`LLM_MODEL=openai/gpt-oss-120b`, and `EMBEDDING_PROVIDER=hash`. No code changes needed to swap
models or providers. `.env` files are git-ignored — never commit keys.

### Uploading documents (UI)
The **Ingest** tab (`/ingest`) is the upload surface: drag & drop PDFs/images/spreadsheets,
it POSTs to `POST /api/v1/documents/upload`. Each upload is written as a **durable ingestion
job** (`ingestion_jobs` table) and executed by a background task; `GET /api/v1/documents`
polling shows every document until processed. On restart, `resume_stale_jobs` re-queues
anything left mid-flight, so an interrupted upload resumes rather than hanging forever.
Extracted facts then flow to Chat (cited answers), Reports, and the Review Queue.

## Roadmap (next milestones)
1. ✅ Document ingestion + routing (scanned vs digital vs image)
2. ✅ Extraction & normalized schema (`entity, value, unit, date, source_ref`)
3. ✅ Validation / conflict detection + human-in-the-loop review queue
4. ✅ RAG query engine with citations + golden evaluation harness
5. ✅ Report generation templates + facts lint + professional PDF (cover/TOC/charts)
6. ⬜ Durable job system done — next: worker improvement (retry UI/backoff tuning)
7. ⬜ Review-passcode auth (real `resolved_by` identity), frontend report preview + trend charts
8. ⬜ CI (GitHub Actions: pytest + RAG eval + report lint), deploy configs (Render/Vercel/Netlify)

## License
Prototype — hackathon use.