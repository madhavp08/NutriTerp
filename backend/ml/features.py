"""Feature engineering: (user profile, menu item) -> one numeric row.

This single module is used by BOTH training (pandas DataFrame of many rows)
and serving (same function, a handful of candidate rows), so the model can
never see training features that disagree with serving features — the
classic "training/serving skew" bug is impossible by construction.

Feature groups:
- nutrition: raw label numbers plus derived densities
- cuisine:   keyword flags from the dish name (cheap but effective)
- dietary:   the scraped legend icons as 0/1 flags
- user:      goal and calorie budget from the questionnaire
- interaction: how the item matches THIS user's budget
"""

import pandas as pd

from app.models import MenuItem, Profile
from app.profile import calorie_target, meal_budget

# Order matters: this list IS the model's input schema. Append new features
# at the end and retrain; never reorder, or old artifacts become garbage.
FEATURE_COLUMNS = [
    # nutrition
    "calories", "protein_g", "total_fat_g", "carbs_g", "fiber_g",
    "sugars_g", "added_sugars_g", "sodium_mg",
    "protein_per_100kcal", "sugar_per_100kcal",
    # cuisine keywords from the name
    "cuisine_asian", "cuisine_mexican", "cuisine_italian",
    "cuisine_american", "cuisine_indian", "cuisine_mediterranean",
    "cuisine_breakfast",
    # dietary icon flags
    "flag_vegan", "flag_vegetarian", "flag_halal_friendly",
    # user
    "goal_lose", "goal_gain", "user_budget",
    # interaction (user x item)
    "budget_fit", "over_budget",
]

CUISINE_KEYWORDS = {
    "cuisine_asian": ("asian", "teriyaki", "stir fry", "lo mein", "pad thai",
                      "korean", "kimchi", "gochujang", "sesame", "mongolian",
                      "szechuan", "ramen", "sushi", "thai", "bokkeum"),
    "cuisine_mexican": ("taco", "quesadilla", "burrito", "enchilada", "salsa",
                        "mexican", "mole", "arroz", "elote", "fajita", "chipotle"),
    "cuisine_italian": ("pasta", "penne", "alfredo", "marinara", "parmesan",
                        "pizza", "italian", "lasagna", "risotto", "pesto"),
    "cuisine_american": ("burger", "cheeseburger", "hot dog", "mac and cheese",
                         "bbq", "fried chicken", "grilled cheese", "meatloaf"),
    "cuisine_indian": ("curry", "tikka", "masala", "tandoori", "dal", "naan"),
    "cuisine_mediterranean": ("hummus", "falafel", "gyro", "pita", "greek",
                              "mediterranean", "tzatziki", "shawarma"),
    "cuisine_breakfast": ("egg", "pancake", "waffle", "french toast", "bagel",
                          "oatmeal", "sausage", "bacon", "smoothie", "yogurt"),
}


def item_features(item: MenuItem) -> dict:
    """Features that depend only on the menu item (cacheable)."""
    calories = item.calories or 0.0
    name = item.name.lower()
    flags = item.flags

    row = {
        "calories": calories,
        "protein_g": item.protein_g or 0.0,
        "total_fat_g": item.total_fat_g or 0.0,
        "carbs_g": item.carbs_g or 0.0,
        "fiber_g": item.fiber_g or 0.0,
        "sugars_g": item.sugars_g or 0.0,
        "added_sugars_g": item.added_sugars_g or 0.0,
        "sodium_mg": item.sodium_mg or 0.0,
        "protein_per_100kcal": (item.protein_g or 0.0) / max(calories, 1) * 100,
        "sugar_per_100kcal": (item.sugars_g or 0.0) / max(calories, 1) * 100,
        "flag_vegan": float("vegan" in flags),
        "flag_vegetarian": float("vegetarian" in flags or "vegan" in flags),
        "flag_halal_friendly": float("halal_friendly" in flags),
    }
    for column, keywords in CUISINE_KEYWORDS.items():
        row[column] = float(any(k in name for k in keywords))
    return row


def pair_features(profile: Profile, item: MenuItem) -> dict:
    """The full feature row for one (user, item) pair."""
    budget = meal_budget(profile, calorie_target(profile))
    calories = item.calories or 0.0
    row = item_features(item)
    row.update({
        "goal_lose": float(profile.goal == "lose"),
        "goal_gain": float(profile.goal == "gain"),
        "user_budget": float(budget),
        "budget_fit": max(0.0, 1.0 - abs(calories - budget) / budget),
        "over_budget": float(calories > budget),
    })
    return row


def to_frame(rows: list[dict]) -> pd.DataFrame:
    """Dict rows -> DataFrame with columns in canonical order."""
    return pd.DataFrame(rows, columns=FEATURE_COLUMNS)
