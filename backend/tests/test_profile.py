"""Profile questionnaire tests, including the calorie formula."""

from app.models import Profile
from app.profile import calorie_target

CREDS = {"email": "terp@umd.edu", "password": "correct-horse-battery"}

FULL_PROFILE = {
    "dietary_pattern": "vegetarian",
    "avoid_allergens": ["nuts", "shellfish"],
    "avoid_pork": True,
    "avoid_alcohol": False,
    "goal": "lose",
    "sex": "male",
    "age_years": 20,
    "height_cm": 178,
    "weight_kg": 75,
    "activity_level": "moderate",
    "taste_note": "Love spicy asian food, not a fan of mushrooms.",
}


def signup(client):
    client.post("/api/auth/signup", json=CREDS)


def test_profile_requires_login(client):
    assert client.get("/api/profile").status_code == 401
    assert client.put("/api/profile", json=FULL_PROFILE).status_code == 401


def test_profile_missing_before_first_save(client):
    signup(client)
    assert client.get("/api/profile").json() == {"exists": False}


def test_save_and_read_back(client):
    signup(client)
    saved = client.put("/api/profile", json=FULL_PROFILE).json()
    assert saved["dietary_pattern"] == "vegetarian"
    assert sorted(saved["avoid_allergens"]) == ["nuts", "shellfish"]

    read = client.get("/api/profile").json()
    assert read["exists"] is True
    assert read["taste_note"] == FULL_PROFILE["taste_note"]


def test_calorie_target_formula():
    # Mifflin-St Jeor by hand: 10*75 + 6.25*178 - 5*20 + 5 = 1767.5 BMR
    # TDEE = 1767.5 * 1.55 = 2739.6; lose = -400 -> 2340
    profile = Profile(
        goal="lose", sex="male", age_years=20,
        height_cm=178, weight_kg=75, activity_level="moderate",
    )
    assert calorie_target(profile) == 2340


def test_calorie_target_none_without_body_info(client):
    signup(client)
    minimal = {"dietary_pattern": "none", "goal": "maintain"}
    saved = client.put("/api/profile", json=minimal).json()
    assert saved["calorie_target"] is None


def test_partial_body_info_rejected(client):
    signup(client)
    partial = {**FULL_PROFILE, "weight_kg": None}
    assert client.put("/api/profile", json=partial).status_code == 422


def test_update_overwrites(client):
    signup(client)
    client.put("/api/profile", json=FULL_PROFILE)
    client.put("/api/profile", json={"dietary_pattern": "vegan", "goal": "gain"})
    read = client.get("/api/profile").json()
    assert read["dietary_pattern"] == "vegan"
    assert read["avoid_allergens"] == []


def test_unknown_allergen_rejected(client):
    signup(client)
    bad = {**FULL_PROFILE, "avoid_allergens": ["plutonium"]}
    assert client.put("/api/profile", json=bad).status_code == 422
