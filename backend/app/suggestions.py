"""Suggestion and feedback endpoints.

GET /api/suggestions        -> today's breakfast / lunch / dinner pick
POST /api/feedback          -> thumbs up / down on a menu item
"""

import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

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
from ml.rerank import choose
from .profile import calorie_target, meal_budget
from .recommend import eligible, is_main_dish, rank

router = APIRouter(prefix="/api", tags=["suggestions"])


@router.get("/suggestions")
def suggestions(
    user: User = Depends(current_user), session: Session = Depends(get_session)
) -> dict:
    profile = session.scalar(select(Profile).where(Profile.user_id == user.id))
    if profile is None:
        raise HTTPException(status_code=409, detail="Complete the questionnaire first")

    today = datetime.date.today()
    budget = meal_budget(profile, calorie_target(profile))

    # The user's existing thumbs, keyed by item id, to render button state.
    feedback = {
        fb.menu_item_id: fb.liked
        for fb in session.scalars(
            select(MealFeedback).where(MealFeedback.user_id == user.id)
        )
    }

    rows = session.execute(
        select(MenuOffering, MenuItem)
        .join(MenuItem, MenuOffering.menu_item_id == MenuItem.id)
        .where(MenuOffering.date == today)
    ).all()

    result: dict[str, dict | None] = {}
    already_suggested: set[int] = set()
    for meal in MEALS:
        candidates = []
        for offering, item in rows:
            if offering.meal != meal:
                continue
            if not is_main_dish(offering.station, item):
                continue
            if not eligible(profile, item):
                continue
            scored = rank(profile, item, budget)
            candidates.append((scored, offering, item))
        picked = choose(candidates, already_suggested, profile.taste_note)
        if picked is None:
            result[meal] = None
            continue
        scored, offering, item = picked
        already_suggested.add(item.id)
        result[meal] = {
            "menu_item_id": item.id,
            "name": item.name,
            "hall": HALLS.get(offering.hall_id, str(offering.hall_id)),
            "station": offering.station,
            "calories": item.calories,
            "protein_g": item.protein_g,
            "carbs_g": item.carbs_g,
            "total_fat_g": item.total_fat_g,
            "diet_flags": sorted(item.flags),
            "reasons": scored.reasons,
            "liked": feedback.get(item.id),
        }

    return {
        "date": today.isoformat(),
        "meal_budget": budget,
        "calorie_target": calorie_target(profile),
        "meals": result,
    }


class FeedbackIn(BaseModel):
    menu_item_id: int
    liked: bool


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
    return {"menu_item_id": data.menu_item_id, "liked": data.liked}
