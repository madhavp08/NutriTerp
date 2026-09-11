"""Suggestion and feedback endpoints.

GET /api/suggestions  -> 9 picks: one breakfast/lunch/dinner per dining hall
POST /api/feedback    -> thumbs up / down; a dislike swaps ONLY that hall+meal
"""

import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ml.rerank import choose

from .auth import current_user
from .db import get_session
from .models import (
    HALLS,
    MEALS,
    MealFeedback,
    MenuItem,
    MenuOffering,
    Profile,
    User,
)
from .profile import calorie_target, meal_budget
from .recommend import eligible, is_main_dish, rank

router = APIRouter(prefix="/api", tags=["suggestions"])


def _card(offering: MenuOffering, item: MenuItem, scored, liked: bool | None) -> dict:
    return {
        "menu_item_id": item.id,
        "name": item.name,
        "hall_id": offering.hall_id,
        "hall": HALLS.get(offering.hall_id, str(offering.hall_id)),
        "meal": offering.meal,
        "station": offering.station,
        "calories": item.calories,
        "protein_g": item.protein_g,
        "carbs_g": item.carbs_g,
        "total_fat_g": item.total_fat_g,
        "diet_flags": sorted(item.flags),
        "reasons": scored.reasons,
        "liked": liked,
    }


def _pick_slot(rows, profile, budget, hall_id: int, meal: str,
               banned: set[int], already: set[int]):
    """Best eligible dish for one hall+meal, skipping banned/already-shown ids."""
    candidates = []
    for offering, item in rows:
        if offering.hall_id != hall_id or offering.meal != meal:
            continue
        if item.id in banned:
            continue
        if not is_main_dish(offering.station, item):
            continue
        if not eligible(profile, item):
            continue
        candidates.append((rank(profile, item, budget), offering, item))
    return choose(candidates, already, profile.taste_note)


def _todays_rows(session: Session, today: datetime.date):
    return session.execute(
        select(MenuOffering, MenuItem)
        .join(MenuItem, MenuOffering.menu_item_id == MenuItem.id)
        .where(MenuOffering.date == today)
    ).all()


def _disliked_ids(session: Session, user_id: int) -> set[int]:
    return {
        fb.menu_item_id
        for fb in session.scalars(
            select(MealFeedback).where(
                MealFeedback.user_id == user_id, MealFeedback.liked.is_(False)
            )
        )
    }


def _liked_map(session: Session, user_id: int) -> dict[int, bool]:
    return {
        fb.menu_item_id: fb.liked
        for fb in session.scalars(
            select(MealFeedback).where(MealFeedback.user_id == user_id)
        )
    }


@router.get("/suggestions")
def suggestions(
    user: User = Depends(current_user), session: Session = Depends(get_session)
) -> dict:
    profile = session.scalar(select(Profile).where(Profile.user_id == user.id))
    if profile is None:
        raise HTTPException(status_code=409, detail="Complete the questionnaire first")

    today = datetime.date.today()
    budget = meal_budget(profile, calorie_target(profile))
    feedback = _liked_map(session, user.id)
    banned = {item_id for item_id, liked in feedback.items() if liked is False}
    rows = _todays_rows(session, today)

    halls = []
    for hall_id, hall_name in HALLS.items():
        # Dedupe only inside one hall so lunch/dinner do not repeat. The
        # same dish may appear at two halls — the user is choosing where
        # to eat, not getting one global plate.
        already: set[int] = set()
        meals: dict[str, dict | None] = {}
        for meal in MEALS:
            picked = _pick_slot(rows, profile, budget, hall_id, meal, banned, already)
            if picked is None:
                meals[meal] = None
                continue
            scored, offering, item = picked
            already.add(item.id)
            meals[meal] = _card(offering, item, scored, feedback.get(item.id))
        halls.append({"hall_id": hall_id, "name": hall_name, "meals": meals})

    return {
        "date": today.isoformat(),
        "meal_budget": budget,
        "calorie_target": calorie_target(profile),
        "halls": halls,
    }


class FeedbackIn(BaseModel):
    menu_item_id: int
    liked: bool
    hall_id: int | None = None
    meal: str | None = Field(default=None, pattern="^(breakfast|lunch|dinner)$")


@router.post("/feedback")
def give_feedback(
    data: FeedbackIn,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict:
    if session.get(MenuItem, data.menu_item_id) is None:
        raise HTTPException(status_code=404, detail="Unknown menu item")

    row = session.scalar(
        select(MealFeedback).where(
            MealFeedback.user_id == user.id,
            MealFeedback.menu_item_id == data.menu_item_id,
        )
    )
    if row is None:
        row = MealFeedback(user_id=user.id, menu_item_id=data.menu_item_id, liked=data.liked)
        session.add(row)
    else:
        row.liked = data.liked
    session.commit()

    replacement = None
    # Dislike swaps only this hall+meal. Other eight cards stay put.
    if not data.liked and data.hall_id is not None and data.meal:
        profile = session.scalar(select(Profile).where(Profile.user_id == user.id))
        if profile is not None:
            today = datetime.date.today()
            budget = meal_budget(profile, calorie_target(profile))
            banned = _disliked_ids(session, user.id)
            banned.add(data.menu_item_id)
            picked = _pick_slot(
                _todays_rows(session, today),
                profile, budget, data.hall_id, data.meal, banned, set(),
            )
            if picked is not None:
                scored, offering, item = picked
                replacement = _card(offering, item, scored, None)

    return {
        "menu_item_id": data.menu_item_id,
        "liked": data.liked,
        "replacement": replacement,
    }
