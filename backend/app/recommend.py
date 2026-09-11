"""Meal suggestions: hard filters + an explainable baseline score.

Two stages, deliberately separated:

1. eligible(profile, item)  — HARD filters. A meal that violates the diet,
   an allergy, or a pork/alcohol rule is removed, never just down-ranked.
2. rank(profile, item)      — soft ranking of what survived. Uses the
   trained logistic-regression / XGBoost artifact when present; otherwise
   the hand-written heuristic in score(). Hard filters never change.

The same profile + same menu always produce the same suggestions, so the
home page stays stable ("static") between visits.
"""

from dataclasses import dataclass
from pathlib import Path

from .models import MenuItem, Profile

# User allergen choice -> substrings looked for in the label's ALLERGENS
# text (e.g. "Tree Nuts, Peanuts, Gluten"). The scraped icon flags cover
# most items, but the label text catches recipes whose icons are missing.
ALLERGEN_TEXT_MARKERS: dict[str, tuple[str, ...]] = {
    "dairy": ("dairy", "milk"),
    "egg": ("egg",),
    "fish": ("fish",),
    "shellfish": ("shellfish", "crustacean"),
    "gluten": ("gluten", "wheat"),
    "soy": ("soy",),
    "sesame": ("sesame",),
    "nuts": ("tree nuts", "peanut", "almond", "cashew", "pecan", "walnut"),
    "coconut": ("coconut",),
}

# Stations that never contain a main dish worth suggesting on its own.
STATION_SKIP_MARKERS = ("sides", "treats", "dessert", "soup du jour", "bagel bar")
# Single-ingredient condiments the ranker otherwise loves (tiny, calorie-dense).
NAME_SKIP_MARKERS = (
    "olive oil", "canola oil", "vegetable oil", "vinaigrette",
    "mayonnaise", "earth balance", "sauce (rtu)",
)

# Below this many calories an item is a condiment or garnish, not a meal.
MIN_MEAL_CALORIES = 250

# Trained ranker written by `python -m ml.train`. Missing = use the heuristic.
RANKER_PATH = Path(__file__).resolve().parent.parent / "ml" / "artifacts" / "ranker.joblib"
_ranker: dict | None = None
_ranker_loaded = False


def eligible(profile: Profile, item: MenuItem) -> bool:
    """Hard filters. False means: never show this item to this user."""
    flags = item.flags
    allergen_text = (item.allergens or "").lower()

    if profile.dietary_pattern == "vegan" and "vegan" not in flags:
        return False
    if profile.dietary_pattern == "vegetarian" and not flags & {"vegan", "vegetarian"}:
        return False
    if profile.dietary_pattern == "halal" and "halal_friendly" not in flags:
        return False

    if profile.avoid_pork and "pork" in flags:
        return False
    if profile.avoid_alcohol and ("alcohol" in flags or "alcohol" in allergen_text):
        return False

    for allergen in profile.avoid_allergens.split(","):
        if not allergen:
            continue
        if allergen in flags:
            return False
        if any(marker in allergen_text for marker in ALLERGEN_TEXT_MARKERS[allergen]):
            return False
    return True


def get_ranker() -> dict | None:
    """Load the trained model once. None means "use the heuristic"."""
    global _ranker, _ranker_loaded
    if not _ranker_loaded:
        _ranker_loaded = True
        if RANKER_PATH.exists():
            import joblib
            _ranker = joblib.load(RANKER_PATH)
    return _ranker


def reset_ranker_cache() -> None:
    """Tests call this after pointing RANKER_PATH at a fake artifact."""
    global _ranker, _ranker_loaded
    _ranker = None
    _ranker_loaded = False


@dataclass
class Scored:
    score: float
    reasons: list[str]


def score(profile: Profile, item: MenuItem, budget: int) -> Scored:
    """Baseline heuristic, in plain words:

    - protein density is good (more protein per calorie),
    - landing near the per-meal calorie budget is good,
    - fiber is a small bonus, added sugar a small penalty,
    - "lose" cares more about the budget, "gain" cares more about protein.

    Every term is scaled to roughly [0, 1] so the weights mean something.
    """
    calories = item.calories or 0.0
    protein = item.protein_g or 0.0
    fiber = item.fiber_g or 0.0
    added_sugar = item.added_sugars_g or 0.0

    reasons: list[str] = []

    protein_density = min(protein / max(calories, 1) * 10, 1.0)  # 1.0 at 10g/100kcal
    if protein >= 20:
        reasons.append(f"{protein:.0f}g protein")

    budget_fit = max(0.0, 1.0 - abs(calories - budget) / budget)
    if abs(calories - budget) <= budget * 0.25:
        reasons.append(f"~{calories:.0f} kcal fits your {budget} kcal meal budget")

    fiber_bonus = min(fiber / 10, 1.0)
    if fiber >= 5:
        reasons.append(f"{fiber:.0f}g fiber")

    sugar_penalty = min(added_sugar / 25, 1.0)
    if added_sugar >= 15:
        reasons.append(f"high added sugar ({added_sugar:.0f}g)")

    if profile.goal == "lose":
        weights = (2.0, 2.0, 1.0, -1.5)
    elif profile.goal == "gain":
        weights = (3.0, 1.0, 0.5, -0.5)
    else:  # maintain
        weights = (2.0, 1.5, 1.0, -1.0)

    total = (
        weights[0] * protein_density
        + weights[1] * budget_fit
        + weights[2] * fiber_bonus
        + weights[3] * sugar_penalty
    )
    return Scored(score=total, reasons=reasons)


def rank(profile: Profile, item: MenuItem, budget: int) -> Scored:
    """Heuristic reasons, plus the trained model's P(like) when one exists.

    The heuristic stays the fallback AND the explanation. The model only
    replaces the numeric score used to pick a winner, so a missing artifact
    never changes what the user sees.
    """
    heuristic = score(profile, item, budget)
    ranker = get_ranker()
    if ranker is None:
        return heuristic
    from ml.features import pair_features, to_frame
    frame = to_frame([pair_features(profile, item)])
    proba = float(ranker["model"].predict_proba(frame)[0, 1])
    reasons = list(heuristic.reasons)
    reasons.append("learned from past likes")
    return Scored(score=proba, reasons=reasons)


def is_main_dish(station: str, item: MenuItem) -> bool:
    """Heuristic: skip sides/treats stations and condiment-sized items."""
    station_lower = station.lower()
    if any(marker in station_lower for marker in STATION_SKIP_MARKERS):
        return False
    name_lower = item.name.lower()
    if any(marker in name_lower for marker in NAME_SKIP_MARKERS):
        return False
    return (item.calories or 0) >= MIN_MEAL_CALORIES
