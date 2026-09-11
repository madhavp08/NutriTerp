"""API tests for 9-slot suggestions and dislike-to-swap."""

import datetime

from sqlalchemy.orm import Session

from app.models import HALLS, MEALS, MenuItem, MenuOffering

CREDS = {"email": "terp@umd.edu", "password": "correct-horse-battery"}


def slot(payload, hall_id, meal):
    hall = next(h for h in payload["halls"] if h["hall_id"] == hall_id)
    return hall["meals"][meal]


def seed_menu(client):
    """Two breakfast items at South Campus: eggs (better) and a donut."""
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
    assert len(first["halls"]) == 3
    assert slot(first, 16, "breakfast")["menu_item_id"] == ids["eggs"]
    assert slot(first, 16, "lunch") is None
    assert slot(first, 19, "breakfast") is None
    second = client.get("/api/suggestions").json()
    assert first["halls"] == second["halls"]


def test_vegetarian_never_sees_pork_even_if_it_scores_best(client):
    seed_menu(client)
    setup_user(client, dietary_pattern="vegetarian")
    meal = slot(client.get("/api/suggestions").json(), 16, "breakfast")
    assert meal["name"] != "Bacon Skillet"


def test_like_roundtrip(client):
    ids = seed_menu(client)
    setup_user(client)
    assert client.post("/api/feedback", json={
        "menu_item_id": ids["eggs"], "liked": True, "hall_id": 16, "meal": "breakfast",
    }).status_code == 200
    assert slot(client.get("/api/suggestions").json(), 16, "breakfast")["liked"] is True


def test_dislike_swaps_only_that_hall_and_meal(client):
    """Dislike replaces one card. The other eight slots stay as they were."""
    with Session(client.engine) as s:
        eggs = MenuItem(recipe_id="eggs", name="Scrambled Eggs", calories=300, protein_g=24)
        donut = MenuItem(recipe_id="donut", name="Frosted Donut", calories=420, protein_g=4,
                         added_sugars_g=30)
        salmon = MenuItem(recipe_id="salmon", name="Lemon Salmon", calories=480, protein_g=38)
        s.add_all([eggs, donut, salmon])
        s.flush()
        today = datetime.date.today()
        for it in (eggs, donut):
            s.add(MenuOffering(date=today, hall_id=16, meal="breakfast",
                               station="Chef's Table", menu_item_id=it.id))
        s.add(MenuOffering(date=today, hall_id=19, meal="breakfast",
                           station="Purple Zone", menu_item_id=salmon.id))
        s.add(MenuOffering(date=today, hall_id=16, meal="lunch",
                           station="Roaster", menu_item_id=salmon.id))
        s.commit()
        eggs_id, donut_id, salmon_id = eggs.id, donut.id, salmon.id

    setup_user(client)
    before = client.get("/api/suggestions").json()
    assert slot(before, 16, "breakfast")["menu_item_id"] == eggs_id
    yah_before = slot(before, 19, "breakfast")["menu_item_id"]
    lunch_before = slot(before, 16, "lunch")["menu_item_id"]

    resp = client.post("/api/feedback", json={
        "menu_item_id": eggs_id, "liked": False, "hall_id": 16, "meal": "breakfast",
    }).json()
    assert resp["replacement"]["menu_item_id"] == donut_id

    after = client.get("/api/suggestions").json()
    assert slot(after, 16, "breakfast")["menu_item_id"] == donut_id
    assert slot(after, 19, "breakfast")["menu_item_id"] == yah_before == salmon_id
    assert slot(after, 16, "lunch")["menu_item_id"] == lunch_before


def test_feedback_unknown_item_404(client):
    setup_user(client)
    assert client.post("/api/feedback", json={"menu_item_id": 99999, "liked": True}).status_code == 404


def test_no_duplicate_dish_across_meals_in_one_hall(client):
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
    halls = client.get("/api/suggestions").json()
    assert slot(halls, 16, "lunch")["menu_item_id"] == star_id
    assert slot(halls, 16, "dinner")["menu_item_id"] == okay_id


def test_one_slot_per_hall_and_meal(client):
    with Session(client.engine) as s:
        today = datetime.date.today()
        for hall_id in HALLS:
            for meal in MEALS:
                item = MenuItem(
                    recipe_id=f"{hall_id}-{meal}",
                    name=f"{HALLS[hall_id]} {meal} special",
                    calories=500, protein_g=25,
                )
                s.add(item)
                s.flush()
                s.add(MenuOffering(date=today, hall_id=hall_id, meal=meal,
                                   station="Chef's Table", menu_item_id=item.id))
        s.commit()

    setup_user(client)
    payload = client.get("/api/suggestions").json()
    filled = [
        slot(payload, h, m)
        for h in HALLS
        for m in MEALS
    ]
    assert all(card is not None for card in filled)
    assert len({(c["hall_id"], c["meal"]) for c in filled}) == 9
