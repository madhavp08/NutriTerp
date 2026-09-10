"""FastAPI entry point.

Run locally with:
    cd backend && uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from .auth import router as auth_router
from .db import Base, engine, get_session


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Create any missing tables on startup. No-op when they already exist."""
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="NutriTerp API", lifespan=lifespan)
app.include_router(auth_router)


@app.get("/api/health")
def health(session: Session = Depends(get_session)) -> dict:
    """Liveness check that also proves the database is reachable."""
    session.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}
