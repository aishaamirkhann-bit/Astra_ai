"""
App entrypoint. Run with:
    uvicorn app.main:app --reload
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, engine
from app.api.v1.router import api_router
from app.websockets.pipeline_ws import router as pipeline_ws_router

# Import models so Base.metadata knows about every table before create_all runs.
import app.models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dev convenience — creates tables if they don't exist yet.
    # In production, use Alembic migrations instead (see README).
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title=settings.APP_NAME, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(pipeline_ws_router)


@app.get("/health")
def health_check():
    return {"status": "ok", "app": settings.APP_NAME}
