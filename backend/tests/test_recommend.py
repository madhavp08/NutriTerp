"""Unit tests for hard filters and the baseline scorer (no HTTP, no DB)."""

from app.models import MenuItem, Profile
from app.profile import meal_budget
from app.recommend import eligible, is_main_dish, score


def item(**kwargs) -> MenuItem:
    defaults = dict(recipe_id="r", name="Test Dish", diet_flags="", allergens=None)
    return MenuItem(**{**defaults, **kwargs})


def profile(**kwargs) -> Profile:
    defaults = dict(
        dietary_pattern="none", avoid_allergens="", avoid_pork=False,
        avoid_alcohol=False, goal="maintain",
    )
    return Profile(**{**defaults, **kwargs})


# ---------- hard filters ----------

def test_vegan_only_sees_vegan():
    p = profile(dietary_pattern="vegan")
    assert eligible(p, item(diet_flags="vegan"))
    assert not eligible(p, item(diet_flags="vegetarian"))
    assert not eligible(p, item(diet_flags=""))


def test_vegetarian_accepts_vegan_too():
    p = profile(dietary_pattern="vegetarian")
    assert eligible(p, item(diet_flags="vegan"))
    assert eligible(p, item(diet_flags="vegetarian,egg"))
    assert not eligible(p, item(diet_flags="pork"))


def test_halal_requires_flag():
    p = profile(dietary_pattern="halal")
    assert eligible(p, item(diet_flags="halal_friendly"))
    assert not eligible(p, item(diet_flags="vegan"))


def test_pork_and_alcohol_avoidance():
    assert not eligible(profile(avoid_pork=True), item(diet_flags="pork"))
    assert not eligible(profile(avoid_alcohol=True), item(diet_flags="alcohol"))
    assert not eligible(
        profile(avoid_alcohol=True), item(allergens="Dairy, Alcohol")
    )


def test_allergen_blocked_by_flag_or_label_text():
    p = profile(avoid_allergens="nuts")
    assert not eligible(p, item(diet_flags="nuts"))
    assert not eligible(p, item(allergens="Tree Nuts, Gluten"))
    assert not eligible(p, item(allergens="contains PEANUT butter"))
    assert eligible(p, item(diet_flags="dairy", allergens="Dairy"))


# ---------- scoring ----------

def test_high_protein_beats_junk_for_every_goal():
    grilled = item(calories=500, protein_g=45, fiber_g=3, added_sugars_g=0)
    cake = item(calories=500, protein_g=4, fiber_g=1, added_sugars_g=40)
    for goal in ("lose", "maintain", "gain"):
        p = profile(goal=goal)
        assert score(p, grilled, 750).score > score(p, cake, 750).score


def test_budget_fit_matters_more_when_losing():
    p_lose, p_gain = profile(goal="lose"), profile(goal="gain")
    huge = item(calories=1400, protein_g=60)
    fitting = item(calories=700, protein_g=35)
    lose_gap = score(p_lose, fitting, 700).score - score(p_lose, huge, 700).score
    gain_gap = score(p_gain, fitting, 700).score - score(p_gain, huge, 700).score
    assert lose_gap > gain_gap  # losing punishes the oversized meal harder


def test_reasons_are_human_readable():
    scored = score(profile(), item(calories=700, protein_g=42, fiber_g=8), 750)
    assert any("protein" in r for r in scored.reasons)
    assert any("fiber" in r for r in scored.reasons)


# ---------- main-dish heuristic and budget ----------

def test_sides_and_tiny_items_are_not_mains():
    assert not is_main_dish("Grill Works Sides", item(calories=400))
    assert not is_main_dish("Treats", item(calories=400))
    assert not is_main_dish("Grill Works", item(calories=90))  # condiment-sized
    assert is_main_dish("Grill Works", item(calories=520))
    assert not is_main_dish("Salad Bar", item(name="Olive Oil", calories=251))


def test_meal_budget_third_of_target_or_default():
    assert meal_budget(profile(), None) == 750
    assert meal_budget(profile(), 2340) == 780
