"""Synthetic feedback generator — practice data for the ML pipeline.

Real thumbs from real users are the goal, but a brand-new app has almost
none (the cold-start problem). This script invents N students with simple,
KNOWN preference personas and has each rate a random sample of scraped menu
items. Because we know the ground-truth personas, we can sanity-check that
the trained models actually discover them (e.g. the "gym rat" persona should
produce a positive protein coefficient).

    python -m ml.simulate            # 40 users, ~60 ratings each
    python -m ml.simulate --wipe     # delete previous synthetic users first

Synthetic users all have emails @synthetic.nutriterp so they are easy to
identify and never collide with real accounts.
"""

import argparse
import random

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db import engine
from app.models import MealFeedback, MenuItem, Profile, User

from .features import item_features

SYNTH_DOMAIN = "synthetic.nutriterp"

# Each persona: which feature pushes them to like an item, and how strongly.
# like-probability = sigmoid(bias + sum(weight * feature)).
PERSONAS = [
    {"name": "gym_rat", "goal": "gain", "weights": {"protein_per_100kcal": 0.55, "cuisine_american": 0.4}},
    {"name": "cutting", "goal": "lose", "weights": {"protein_per_100kcal": 0.4, "sugar_per_100kcal": -0.5, "calories": -0.002}},
    {"name": "veggie_lover", "goal": "maintain", "weights": {"flag_vegetarian": 1.6, "fiber_g": 0.12}},
    {"name": "asian_food_fan", "goal": "maintain", "weights": {"cuisine_asian": 2.2, "cuisine_indian": 1.0}},
    {"name": "sweet_tooth", "goal": "maintain", "weights": {"sugar_per_100kcal": 0.35, "cuisine_breakfast": 0.8}},
]

BIAS = -1.0  # base like rate ~27% before persona preferences kick in


def sigmoid(x: float) -> float:
    import math
    return 1 / (1 + math.exp(-x))


def main(users_count: int, ratings_each: int, wipe: bool, seed: int) -> None:
    rng = random.Random(seed)
    with Session(engine) as session:
        if wipe:
            old = session.scalars(select(User).where(User.email.like(f"%@{SYNTH_DOMAIN}"))).all()
            ids = [u.id for u in old]
            if ids:
                session.execute(delete(MealFeedback).where(MealFeedback.user_id.in_(ids)))
                session.execute(delete(Profile).where(Profile.user_id.in_(ids)))
                session.execute(delete(User).where(User.id.in_(ids)))
                session.commit()
                print(f"wiped {len(ids)} synthetic users")

        items = session.scalars(
            select(MenuItem).where(MenuItem.calories.is_not(None), MenuItem.calories >= 200)
        ).all()
        if len(items) < 50:
            raise SystemExit("Not enough scraped menu items; run the scraper first.")
        features = {item.id: item_features(item) for item in items}

        total = 0
        for i in range(users_count):
            persona = PERSONAS[i % len(PERSONAS)]
            user = User(
                email=f"{persona['name']}_{i}@{SYNTH_DOMAIN}",
                password_hash="synthetic-no-login",
            )
            session.add(user)
            session.flush()
            session.add(Profile(user_id=user.id, goal=persona["goal"]))

            for item in rng.sample(items, min(ratings_each, len(items))):
                signal = BIAS + sum(
                    weight * features[item.id][feature]
                    for feature, weight in persona["weights"].items()
                )
                liked = rng.random() < sigmoid(signal)
                session.add(MealFeedback(user_id=user.id, menu_item_id=item.id, liked=liked))
                total += 1
        session.commit()
        print(f"created {users_count} synthetic users, {total} ratings")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--users", type=int, default=40)
    parser.add_argument("--ratings", type=int, default=60)
    parser.add_argument("--wipe", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    main(args.users, args.ratings, args.wipe, args.seed)
