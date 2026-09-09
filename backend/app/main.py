"""FastAPI entry point.

Run locally with:
    cd backend && uvicorn app.main:app --reload
"""

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import get_session

app = FastAPI(title="NutriTerp API")


@app.get("/api/health")
def health(session: Session = Depends(get_session)) -> dict:
    """Liveness check that also proves the database is reachable."""
    session.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}
