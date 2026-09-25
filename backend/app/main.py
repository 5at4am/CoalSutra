import logging
import threading
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import get_current_user
from app.api.routes.auth import router as auth_router
from app.api.routes.documents import router as documents_router
from app.api.routes.facts import conflicts_router, facts_router
from app.api.routes.health import router as health_router
from app.api.routes.llm import llm_router
from app.api.routes.metrics import metrics_router
from app.api.routes.query import query_router
from app.api.routes.reports import router as reports_router
from app.api.routes.review import review_router
from app.api.routes.topics import topics_router
from app.core.config import settings
from app.core.database import Base, engine
from app.services.ingestion.jobs import resume_stale_jobs

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    def _ensure_schema_in_background():
        # The shipped sqlite demo store predates the telemetry tables; create them
        # idempotently at boot so the demo dashboard works out of the box. Postgres
        # deployments use Alembic instead (migration 0007).
        if engine.dialect.name == "postgresql":
            return
        try:
            Base.metadata.create_all(engine)
        except Exception as exc:  # avoid blocking boot on a brief DB outage
            logger.warning("create_all skipped: %s", exc)

    def _resume_in_background():
        try:
            resume_stale_jobs()
        except Exception as exc:  # avoid blocking boot on a brief DB outage
            logger.warning("resume_stale_jobs skipped: %s", exc)

    threading.Thread(target=_ensure_schema_in_background, daemon=True).start()
    threading.Thread(target=_resume_in_background, daemon=True).start()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    lifespan=lifespan,
    dependencies=[Depends(get_current_user)],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix=settings.API_V1_PREFIX, tags=["auth"])
app.include_router(health_router, prefix=settings.API_V1_PREFIX, tags=["health"])
app.include_router(documents_router, prefix=settings.API_V1_PREFIX, tags=["documents"])
app.include_router(facts_router, prefix=settings.API_V1_PREFIX, tags=["facts"])
app.include_router(conflicts_router, prefix=settings.API_V1_PREFIX, tags=["conflicts"])
app.include_router(query_router, prefix=settings.API_V1_PREFIX, tags=["query"])
app.include_router(reports_router, prefix=settings.API_V1_PREFIX, tags=["reports"])
app.include_router(topics_router, prefix=settings.API_V1_PREFIX, tags=["topics"])
app.include_router(review_router, prefix=settings.API_V1_PREFIX, tags=["review"])
app.include_router(metrics_router, prefix=settings.API_V1_PREFIX, tags=["metrics"])
app.include_router(llm_router, prefix=settings.API_V1_PREFIX, tags=["llm"])


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_error_handler(_request, exc: SQLAlchemyError) -> JSONResponse:
    logger.error("database request failed: %s", exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "Database unavailable, please try again later."},
    )


@app.get("/")
def root():
    return {"message": settings.PROJECT_NAME, "docs": "/docs"}