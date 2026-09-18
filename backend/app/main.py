from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.documents import router as documents_router
from app.api.routes.facts import conflicts_router, facts_router
from app.api.routes.health import router as health_router
from app.api.routes.metrics import metrics_router
from app.api.routes.query import query_router
from app.api.routes.reports import router as reports_router
from app.api.routes.review import review_router
from app.api.routes.topics import topics_router
from app.core.config import settings
from app.services.ingestion.jobs import resume_stale_jobs


@asynccontextmanager
async def lifespan(_app: FastAPI):
    resume_stale_jobs()
    yield


app = FastAPI(title=settings.PROJECT_NAME, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix=settings.API_V1_PREFIX, tags=["health"])
app.include_router(documents_router, prefix=settings.API_V1_PREFIX, tags=["documents"])
app.include_router(facts_router, prefix=settings.API_V1_PREFIX, tags=["facts"])
app.include_router(conflicts_router, prefix=settings.API_V1_PREFIX, tags=["conflicts"])
app.include_router(query_router, prefix=settings.API_V1_PREFIX, tags=["query"])
app.include_router(reports_router, prefix=settings.API_V1_PREFIX, tags=["reports"])
app.include_router(topics_router, prefix=settings.API_V1_PREFIX, tags=["topics"])
app.include_router(review_router, prefix=settings.API_V1_PREFIX, tags=["review"])
app.include_router(metrics_router, prefix=settings.API_V1_PREFIX, tags=["metrics"])


@app.get("/")
def root():
    return {"message": settings.PROJECT_NAME, "docs": "/docs"}