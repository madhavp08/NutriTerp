"""Meal diary, calorie totals, and the photo calendar.

GET    /api/logs?date=YYYY-MM-DD   today's (or any day's) logged foods
POST   /api/logs                   log a meal (JSON or multipart with photo)
DELETE /api/logs/{id}              remove one entry
GET    /api/logs/{id}/photo        the picture, only for the owner
GET    /api/calendar?year=&month=  dates that have at least one meal photo
"""

import datetime
import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import current_user
from .db import get_session
from .models import HALLS, MealLog, MenuItem, Profile, User
from .profile import calorie_target

router = APIRouter(prefix="/api", tags=["logs"])

# backend/uploads/{user_id}/{random}.jpg — git-ignored, never from the client.
UPLOAD_ROOT = Path(__file__).resolve().parent.parent / "uploads"
MAX_PHOTO_BYTES = 5 * 1024 * 1024
MEAL_CHOICES = ("breakfast", "lunch", "dinner", "snack")


def _sniff_ext(data: bytes) -> str | None:
    """Trust magic bytes, not the filename the browser sent."""
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return None


def _save_photo(user_id: int, data: bytes) -> str:
    ext = _sniff_ext(data)
    if ext is None:
        raise HTTPException(status_code=400, detail="Photo must be a JPEG, PNG, or WebP")
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=400, detail="Photo must be 5 MB or smaller")
    folder = UPLOAD_ROOT / str(user_id)
    folder.mkdir(parents=True, exist_ok=True)
    filename = secrets.token_hex(16) + ext
    (folder / filename).write_bytes(data)
    return filename


def _log_dict(row: MealLog) -> dict:
    return {
        "id": row.id,
        "date": row.date.isoformat(),
        "meal": row.meal,
        "hall_id": row.hall_id,
        "hall": HALLS.get(row.hall_id) if row.hall_id else None,
        "menu_item_id": row.menu_item_id,
        "name": row.name,
        "calories": row.calories,
        "protein_g": row.protein_g,
        "has_photo": bool(row.photo_filename),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _parse_date(value: str | None) -> datetime.date:
    if not value:
        return datetime.date.today()
    try:
        return datetime.date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD") from exc


def _day_summary(session: Session, user: User, day: datetime.date) -> dict:
    rows = session.scalars(
        select(MealLog).where(MealLog.user_id == user.id, MealLog.date == day)
        .order_by(MealLog.created_at)
    ).all()
    profile = session.scalar(select(Profile).where(Profile.user_id == user.id))
    target = calorie_target(profile) if profile else None
    eaten = sum(r.calories or 0 for r in rows)
    return {
        "date": day.isoformat(),
        "calorie_target": target,
        "calories_eaten": eaten,
        "remaining": (target - eaten) if target is not None else None,
        "entries": [_log_dict(r) for r in rows],
    }


class LogIn(BaseModel):
    date: str | None = None
    meal: str = Field(pattern="^(breakfast|lunch|dinner|snack)$")
    hall_id: int | None = None
    menu_item_id: int | None = None
    name: str | None = Field(default=None, max_length=255)
    calories: float | None = Field(default=None, ge=0, le=5000)
    protein_g: float | None = Field(default=None, ge=0, le=400)


def _build_log(session: Session, user: User, data: LogIn, photo_filename: str | None) -> MealLog:
    name = (data.name or "").strip()
    calories = data.calories
    protein = data.protein_g
    if data.menu_item_id is not None:
        item = session.get(MenuItem, data.menu_item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Unknown menu item")
        name = name or item.name
        if calories is None:
            calories = item.calories
        if protein is None:
            protein = item.protein_g
    if not name:
        raise HTTPException(status_code=422, detail="Give a meal name or pick a menu item")
    return MealLog(
        user_id=user.id,
        date=_parse_date(data.date),
        meal=data.meal,
        hall_id=data.hall_id,
        menu_item_id=data.menu_item_id,
        name=name,
        calories=calories,
        protein_g=protein,
        photo_filename=photo_filename,
    )


@router.get("/logs")
def list_logs(
    date: str | None = None,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict:
    return _day_summary(session, user, _parse_date(date))


@router.post("/logs")
def create_log(
    data: LogIn,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict:
    row = _build_log(session, user, data, photo_filename=None)
    session.add(row)
    session.commit()
    return _day_summary(session, user, row.date)


@router.post("/logs/photo")
async def create_log_with_photo(
    meal: str = Form(...),
    date: str | None = Form(default=None),
    hall_id: int | None = Form(default=None),
    menu_item_id: int | None = Form(default=None),
    name: str | None = Form(default=None),
    calories: float | None = Form(default=None),
    protein_g: float | None = Form(default=None),
    photo: UploadFile = File(...),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Multipart twin of POST /api/logs, used when the user attaches a picture."""
    if meal not in MEAL_CHOICES:
        raise HTTPException(status_code=422, detail="meal must be breakfast, lunch, dinner, or snack")
    raw = await photo.read()
    filename = _save_photo(user.id, raw)
    payload = LogIn(
        date=date, meal=meal, hall_id=hall_id, menu_item_id=menu_item_id,
        name=name, calories=calories, protein_g=protein_g,
    )
    row = _build_log(session, user, payload, photo_filename=filename)
    session.add(row)
    session.commit()
    return _day_summary(session, user, row.date)


@router.delete("/logs/{log_id}")
def delete_log(
    log_id: int,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict:
    row = session.get(MealLog, log_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="Log not found")
    day = row.date
    if row.photo_filename:
        path = UPLOAD_ROOT / str(user.id) / row.photo_filename
        path.unlink(missing_ok=True)
    session.delete(row)
    session.commit()
    return _day_summary(session, user, day)


@router.get("/logs/{log_id}/photo")
def get_photo(
    log_id: int,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    row = session.get(MealLog, log_id)
    if row is None or row.user_id != user.id or not row.photo_filename:
        raise HTTPException(status_code=404, detail="Photo not found")
    path = UPLOAD_ROOT / str(user.id) / row.photo_filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Photo not found")
    return FileResponse(path)


@router.get("/calendar")
def photo_calendar(
    year: int,
    month: int,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict:
    if month < 1 or month > 12 or year < 2000 or year > 2100:
        raise HTTPException(status_code=400, detail="Invalid year or month")
    rows = session.scalars(
        select(MealLog).where(
            MealLog.user_id == user.id,
            MealLog.photo_filename.is_not(None),
        )
    ).all()
    days = sorted({
        row.date.isoformat()
        for row in rows
        if row.date.year == year and row.date.month == month
    })
    return {"year": year, "month": month, "photo_days": days}
