"""Profile questionnaire API.

GET /api/profile  -> saved answers + computed daily calorie target (or null)
PUT /api/profile  -> upsert answers (idempotent, whole document at once)

The calorie target uses Mifflin-St Jeor, the standard teaching formula:
    men:   BMR = 10*kg + 6.25*cm - 5*age + 5
    women: BMR = 10*kg + 6.25*cm - 5*age - 161
    TDEE  = BMR * activity multiplier
    target = TDEE - 400 (lose) / +0 (maintain) / +400 (gain)
It is computed on the fly, never stored, so it can't go stale.
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import current_user
from .db import get_session
from .models import Profile, User

router = APIRouter(prefix="/api/profile", tags=["profile"])

ACTIVITY_MULTIPLIER = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}

GOAL_ADJUSTMENT = {"lose": -400, "maintain": 0, "gain": +400}
DEFAULT_MEAL_BUDGET = 750  # kcal per meal when no daily target is set


def meal_budget(_profile: Profile, daily_target: int | None) -> int:
    """Rough kcal budget for one meal (a third of the daily target)."""
    return round(daily_target / 3) if daily_target else DEFAULT_MEAL_BUDGET


class ProfileIn(BaseModel):
    dietary_pattern: Literal["none", "vegetarian", "vegan", "halal"] = "none"
    avoid_allergens: list[Literal[
        "dairy", "egg", "fish", "shellfish", "gluten",
        "soy", "sesame", "nuts", "coconut",
    ]] = []
    avoid_pork: bool = False
    avoid_alcohol: bool = False
    goal: Literal["lose", "maintain", "gain"] = "maintain"

    # All-or-nothing optional body block (validated below).
    sex: Literal["male", "female"] | None = None
    age_years: int | None = Field(default=None, ge=13, le=100)
    height_cm: float | None = Field(default=None, ge=100, le=250)
    weight_kg: float | None = Field(default=None, ge=30, le=300)
    activity_level: Literal[
        "sedentary", "light", "moderate", "active", "very_active"
    ] | None = None

    taste_note: str | None = Field(default=None, max_length=500)


def calorie_target(profile: Profile) -> int | None:
    """Daily calorie target, or None when body info was not provided."""
    if None in (profile.sex, profile.age_years, profile.height_cm,
                profile.weight_kg, profile.activity_level):
        return None
    bmr = (
        10 * profile.weight_kg
        + 6.25 * profile.height_cm
        - 5 * profile.age_years
        + (5 if profile.sex == "male" else -161)
    )
    tdee = bmr * ACTIVITY_MULTIPLIER[profile.activity_level]
    return round(tdee + GOAL_ADJUSTMENT[profile.goal])


def _to_dict(profile: Profile) -> dict:
    return {
        "dietary_pattern": profile.dietary_pattern,
        "avoid_allergens": profile.avoid_allergens.split(",") if profile.avoid_allergens else [],
        "avoid_pork": profile.avoid_pork,
        "avoid_alcohol": profile.avoid_alcohol,
        "goal": profile.goal,
        "sex": profile.sex,
        "age_years": profile.age_years,
        "height_cm": profile.height_cm,
        "weight_kg": profile.weight_kg,
        "activity_level": profile.activity_level,
        "taste_note": profile.taste_note,
        "calorie_target": calorie_target(profile),
    }


@router.get("")
def get_profile(
    user: User = Depends(current_user), session: Session = Depends(get_session)
) -> dict:
    profile = session.scalar(select(Profile).where(Profile.user_id == user.id))
    if profile is None:
        return {"exists": False}
    return {"exists": True, **_to_dict(profile)}


@router.put("")
def put_profile(
    data: ProfileIn,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict:
    body_fields = [data.sex, data.age_years, data.height_cm, data.weight_kg, data.activity_level]
    if any(f is not None for f in body_fields) and any(f is None for f in body_fields):
        raise HTTPException(
            status_code=422,
            detail="Provide all of sex, age, height, weight and activity level — or none of them.",
        )

    profile = session.scalar(select(Profile).where(Profile.user_id == user.id))
    if profile is None:
        profile = Profile(user_id=user.id)
        session.add(profile)

    profile.dietary_pattern = data.dietary_pattern
    profile.avoid_allergens = ",".join(sorted(set(data.avoid_allergens)))
    profile.avoid_pork = data.avoid_pork
    profile.avoid_alcohol = data.avoid_alcohol
    profile.goal = data.goal
    profile.sex = data.sex
    profile.age_years = data.age_years
    profile.height_cm = data.height_cm
    profile.weight_kg = data.weight_kg
    profile.activity_level = data.activity_level
    profile.taste_note = (data.taste_note or "").strip() or None
    session.commit()

    return {"exists": True, **_to_dict(profile)}
