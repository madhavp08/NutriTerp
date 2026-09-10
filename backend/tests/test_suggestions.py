"""API tests for /api/suggestions and /api/feedback."""

import datetime

from sqlalchemy.orm import Session

from app.models import MenuItem, MenuOffering

CREDS = {"email": "terp@umd.edu", "password": "correct-horse-battery"}


def seed_menu(client):
    """Two breakfast items today: one great (eggs), one junk (donut)."""
    with Session(client.engine) as s:
        eggs = MenuItem(recipe_id="eggs", name="Scrambled Eggs", calories=300,
                        protein_g=24, fiber_g=0, added_sugars_g=0,
                        diet_flags="vegetarian,egg")
        donut = MenuItem(recipe_id="donut", name="Frosted Donut", calories=420,
                         protein_g=4, fiber_g=1, added_sugars_g=30,
                         diet_flags="vegetarian,gluten")
        pork = MenuItem(recipe_id="pork", name="Bacon Skillet", calories=500,
                        protein_g=28, diet_flags="pork")
        s.add_all([eggs, donut, pork])
        s.flush()
        today = datetime.date.today()
        for it in (eggs, donut, pork):
            s.add(MenuOffering(date=today, hall_id=16, meal="breakfast",
                               station="Chef's Table", menu_item_id=it.id))
        s.commit()
        return {"eggs": eggs.id, "donut": donut.id, "pork": pork.id}


def setup_user(client, **profile_overrides):
    client.post("/api/auth/signup", json=CREDS)
    profile = {"dietary_pattern": "none", "goal": "maintain", **profile_overrides}
    resp = client.put("/api/profile", json=profile)
    assert resp.status_code == 200


def test_suggestions_require_profile(client):
    client.post("/api/auth/signup", json=CREDS)
    assert client.get("/api/suggestions").status_code == 409


def test_best_breakfast_wins_and_is_deterministic(client):
    ids = seed_menu(client)
    setup_user(client)
    first = client.get("/api/suggestions").json()
    assert first["meals"]["breakfast"]["menu_item_id"] == ids["eggs"]
    assert first["meals"]["lunch"] is None  # nothing seeded for lunch
    second = client.get("/api/suggestions").json()
    assert first["meals"] == second["meals"]  # static between visits


def test_vegetarian_never_sees_pork_even_if_it_scores_best(client):
    seed_menu(client)
    setup_user(client, dietary_pattern="vegetarian")
    meal = client.get("/api/suggestions").json()["meals"]["breakfast"]
    assert meal["name"] != "Bacon Skillet"


def test_feedback_roundtrip_and_overwrite(client):
    ids = seed_menu(client)
    setup_user(client)
    assert client.post("/api/feedback", json={"menu_item_id": ids["eggs"], "liked": True}).status_code == 200
    assert client.get("/api/suggestions").json()["meals"]["breakfast"]["liked"] is True

    client.post("/api/feedback", json={"menu_item_id": ids["eggs"], "liked": False})
    assert client.get("/api/suggestions").json()["meals"]["breakfast"]["liked"] is False


def test_feedback_unknown_item_404(client):
    setup_user(client)
    assert client.post("/api/feedback", json={"menu_item_id": 99999, "liked": True}).status_code == 404


def test_no_duplicate_dish_across_meals_when_alternative_exists(client):
    with Session(client.engine) as s:
        star = MenuItem(recipe_id="star", name="Star Dish", calories=700, protein_g=40)
        okay = MenuItem(recipe_id="okay", name="Okay Dish", calories=650, protein_g=25)
        s.add_all([star, okay])
        s.flush()
        today = datetime.date.today()
        for meal in ("lunch", "dinner"):
            for it in (star, okay):
                s.add(MenuOffering(date=today, hall_id=16, meal=meal,
                                   station="Roaster", menu_item_id=it.id))
        s.commit()
        star_id, okay_id = star.id, okay.id

    setup_user(client)
    meals = client.get("/api/suggestions").json()["meals"]
    # The star dish wins lunch; dinner takes the alternative, not a repeat.
    assert meals["lunch"]["menu_item_id"] == star_id
    assert meals["dinner"]["menu_item_id"] == okay_id
