"""Feature schema, P@K / R@K, and the trained-ranker fallback (no Postgres)."""

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.models import MenuItem, Profile
from app.recommend import rank, reset_ranker_cache, score
from ml.features import FEATURE_COLUMNS, pair_features, to_frame
from ml.train import precision_recall_at_k


def item(**kwargs) -> MenuItem:
    defaults = dict(
        recipe_id="r", name="Teriyaki Chicken Stir Fry",
        calories=520, protein_g=38, total_fat_g=12, carbs_g=40,
        fiber_g=4, sugars_g=8, added_sugars_g=2, sodium_mg=700,
        diet_flags="",
    )
    return MenuItem(**{**defaults, **kwargs})


def profile(**kwargs) -> Profile:
    defaults = dict(
        dietary_pattern="none", avoid_allergens="", avoid_pork=False,
        avoid_alcohol=False, goal="gain",
    )
    return Profile(**{**defaults, **kwargs})


def test_feature_row_has_canonical_columns():
    row = pair_features(profile(), item())
    assert set(row) == set(FEATURE_COLUMNS)
    assert row["cuisine_asian"] == 1.0
    assert row["goal_gain"] == 1.0
    assert row["goal_lose"] == 0.0
    frame = to_frame([row])
    assert list(frame.columns) == FEATURE_COLUMNS


def test_vegan_flag_and_budget_fit():
    vegan = item(name="Tofu Bowl", diet_flags="vegan", calories=750)
    p = profile(goal="maintain")  # no body metrics -> 750 kcal meal budget
    row = pair_features(p, vegan)
    assert row["flag_vegan"] == 1.0
    assert row["flag_vegetarian"] == 1.0
    assert row["over_budget"] == 0.0
    assert row["budget_fit"] == 1.0  # calories == default budget


def test_precision_recall_at_k_ranks_per_user():
    # Two users, four items each. The model scores likes higher.
    frame = pd.DataFrame({
        "user_id": [1, 1, 1, 1, 2, 2, 2, 2],
        "label":   [1, 0, 1, 0, 1, 1, 0, 0],
    })
    scores = np.array([0.9, 0.1, 0.8, 0.2, 0.95, 0.2, 0.85, 0.1])
    # user 1 top-3 by score: 0.9(like), 0.8(like), 0.2(dislike) -> P=2/3, R=2/2
    # user 2 top-3: 0.95(like), 0.85(dislike), 0.2(like) -> P=2/3, R=2/2
    p_at_k, r_at_k = precision_recall_at_k(frame, scores, k=3)
    assert abs(p_at_k - 2 / 3) < 1e-9
    assert abs(r_at_k - 1.0) < 1e-9


def test_rank_falls_back_to_heuristic_without_artifact(monkeypatch, tmp_path):
    from app import recommend as rec
    monkeypatch.setattr(rec, "RANKER_PATH", tmp_path / "missing.joblib")
    reset_ranker_cache()
    p, it = profile(), item()
    assert rank(p, it, 750).score == score(p, it, 750).score
    reset_ranker_cache()


def test_rank_uses_model_probability_when_artifact_exists(monkeypatch, tmp_path):
    from app import recommend as rec

    p, it = profile(), item()
    frame = to_frame([pair_features(p, it)])
    # A tiny "model" that always predicts the positive class with ~0.8.
    pipe = Pipeline([
        ("scale", StandardScaler()),
        ("model", LogisticRegression()),
    ])
    # Need both classes to exist so predict_proba has a column for 1.
    X = pd.concat([frame, frame], ignore_index=True)
    y = [0, 1]
    pipe.fit(X, y)

    path = tmp_path / "ranker.joblib"
    import joblib
    joblib.dump({"model": pipe, "features": FEATURE_COLUMNS, "name": "test"}, path)
    monkeypatch.setattr(rec, "RANKER_PATH", path)
    reset_ranker_cache()

    scored = rank(p, it, 750)
    assert 0.0 <= scored.score <= 1.0
    assert "learned from past likes" in scored.reasons
    reset_ranker_cache()
