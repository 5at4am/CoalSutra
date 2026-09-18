# CoalSutra — CMPDI Reporting Assistant

## Purpose
Smart India Hackathon 2026 prototype (SIH26023) for the **Ministry of Coal / Coal India Limited**:
an AI platform that turns CMPDI/CIL subsidiaries' scattered geological & mining documents
(scanned PDFs, digital PDFs, images, spreadsheets, archives) into structured, queryable,
traceable data. It powers three mandated deliverables:

1. **Automated Report Generation Platform** — extract structured data, validate, auto-fill report templates.
2. **Word Cloud & Topic Identification Module** — topic/theme exploration over the corpus.
3. **AI-Based Query & Response System** — grounded RAG with page-level source citations.

Every extracted number must trace back to a source document + page/paragraph, and a
human-in-the-loop review step gates anything flagged during cross-source validation.

## Folder Structure
```
.
├── backend/                  # Python 3.12, FastAPI
│   ├── app/
│   │   ├── api/routes/       # HTTP endpoints (health → future: ingest, query, reports, topics, review)
│   │   ├── core/             # config (pydantic-settings), database engine/session
│   │   ├── models/           # SQLAlchemy ORM models (Base lives here)
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   └── services/         # business logic: pipeline.py (ingest→…→store), future RAG/report/topic services
│   ├── alembic/              # DB migrations (0001 enables pgvector extension)
│   ├── tests/                # pytest tests (TestClient)
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                 # Next.js 14 (App Router), TypeScript, Tailwind
│   ├── app/                  # layout + pages: /chat, /reports, /dashboard, /review
│   ├── components/           # NavBar
│   └── Dockerfile
├── docker-compose.yml        # db (pgvector) + backend + frontend
├── .env.example              # DATABASE_URL, LLM_API_KEY, OCR_PROVIDER (+ port overrides)
├── CLAUDE.md
└── README.md
```

## Tech Stack
| Layer                 | Choice                                                        |
|-----------------------|---------------------------------------------------------------|
| Backend framework     | FastAPI (Python 3.12) + uvicorn                               |
| ORM / migrations      | SQLAlchemy 2.x + Alembic                                      |
| Postgres              | `pgvector/pgvector:pg16` (PG16 + `vector` extension enabled)  |
| Frontend              | Next.js 14 App Router, TypeScript, Tailwind CSS             |
| OCR (future)          | PaddleOCR / Tesseract / Vision-LLM — chosen via `OCR_PROVIDER`|
| LLM (future)          | generic provider behind `LLM_API_KEY`                          |

## Architecture at a Glance
```
ingest → route → extract → normalize → validate → store
                                │
        ┌───────────────────────┼───────────────────────┐
     query (RAG, cited answers)   report (auto-generate)   topics (word cloud / topic model)
```

- **ingest**: watch upload endpoint / folder for new documents (scanned or digital).
- **route**: classify each document (scanned vs born-digital vs image-heavy) → pick the extraction path.
- **extract**: OCR (scans), native parsing (pdfplumber/pdfminer-style), vision-LLM (maps/diagrams).
- **normalize**: flatten everything into one schema: `entity, value, unit, date, source document, page`.
- **validate**: rules + LLM cross-check new extractions against stored facts; conflicts flagged for human review (never silently overwritten).
- **store**: exact figures in Postgres rows; embeddings + chunks in a vector store (pgvector).
- **query / report / topics**: three consumer modules over the same validated store — this shared
  ingestion/validation backbone is the core of the whole system.

## Commands
- Boot everything: `docker compose up --build` (backend on `:8000`, frontend on `:3000`, db on `:5432`)
- Backend local dev: `uvicorn app.main:app --reload` from `backend/` (set `DATABASE_URL` to localhost)
- Frontend local dev: `npm run dev` from `frontend/`
- Backend tests: `pytest` from `backend/`
- Migrations: `alembic upgrade head` from `backend/`

## Conventions
- No business-logic logic in routes — thin handlers that call `app/services/`.
- All DB access through SQLAlchemy sessions from `app/core/database.py`.
- API responses via Pydantic schemas in `app/schemas/`.
- Frontend pages are server components by default (App Router); client components only where interaction is needed.
- Never commit `.env`. Copy `.env.example` → `.env`.