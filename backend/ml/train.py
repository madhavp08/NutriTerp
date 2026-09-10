"""Train the rankers and report offline metrics.

    python -m ml.train

Steps, in the order they run:
1. Load every (feedback, item, profile) row from Postgres into pandas.
2. Split by USER (not by row): 80% of users train, 20% test. A user's taste
   showing up in both sides would leak information and inflate metrics.
3. Train logistic regression (scaled features, readable coefficients) and
   XGBoost (small trees; learns interactions the linear model can't).
4. Report AUC plus Precision@3 / Recall@3, computed per test user by
   ranking that user's rated items with the model — exactly how the model
   is used in the app (ranking a candidate list), unlike plain accuracy.
5. Save the better-AUC model to ml/artifacts/ranker.joblib; the API picks
   it up on next restart and uses it instead of the hand-written baseline.
"""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import select
from sqlalchemy.orm import Session
from xgboost import XGBClassifier

from app.db import engine
from app.models import MealFeedback, MenuItem, Profile

from .features import FEATURE_COLUMNS, pair_features, to_frame

ARTIFACTS = Path(__file__).parent / "artifacts"
K = 3
MIN_ROWS = 200


def load_dataset() -> pd.DataFrame:
    """One row per feedback: features + label + user_id (for the split)."""
    with Session(engine) as session:
        profiles = {p.user_id: p for p in session.scalars(select(Profile))}
        items = {i.id: i for i in session.scalars(select(MenuItem))}
        rows, labels, users = [], [], []
        for fb in session.scalars(select(MealFeedback)):
            profile = profiles.get(fb.user_id)
            item = items.get(fb.menu_item_id)
            if profile is None or item is None:
                continue
            rows.append(pair_features(profile, item))
            labels.append(int(fb.liked))
            users.append(fb.user_id)
    frame = to_frame(rows)
    frame["label"] = labels
    frame["user_id"] = users
    return frame


def precision_recall_at_k(frame: pd.DataFrame, scores: np.ndarray, k: int) -> tuple[float, float]:
    """Average P@K / R@K over users, ranking each user's items by score."""
    frame = frame.assign(score=scores)
    precisions, recalls = [], []
    for _, group in frame.groupby("user_id"):
        liked_total = int(group["label"].sum())
        if liked_total == 0 or len(group) < k:
            continue  # P@K/R@K are undefined without positives / enough items
        top = group.nlargest(k, "score")
        hits = int(top["label"].sum())
        precisions.append(hits / k)
        recalls.append(hits / liked_total)
    return float(np.mean(precisions)), float(np.mean(recalls))


def main() -> None:
    frame = load_dataset()
    print(f"dataset: {len(frame)} ratings from {frame['user_id'].nunique()} users "
          f"({frame['label'].mean():.0%} liked)")
    if len(frame) < MIN_ROWS:
        raise SystemExit(
            f"Only {len(frame)} ratings — need {MIN_ROWS}+ to train something "
            "meaningful. Rate more meals or run `python -m ml.simulate`."
        )

    # ---- split by user ----
    rng = np.random.default_rng(7)
    user_ids = frame["user_id"].unique()
    rng.shuffle(user_ids)
    cut = int(len(user_ids) * 0.8)
    train = frame[frame["user_id"].isin(user_ids[:cut])]
    test = frame[frame["user_id"].isin(user_ids[cut:])]
    x_train, y_train = train[FEATURE_COLUMNS], train["label"]
    x_test, y_test = test[FEATURE_COLUMNS], test["label"]
    print(f"split: {len(train)} train rows ({cut} users) / {len(test)} test rows "
          f"({len(user_ids) - cut} users)")

    # ---- logistic regression ----
    logreg = Pipeline([
        ("scale", StandardScaler()),  # coefficients comparable across features
        ("model", LogisticRegression(max_iter=2000)),
    ])
    logreg.fit(x_train, y_train)
    logreg_scores = logreg.predict_proba(x_test)[:, 1]

    # ---- xgboost ----
    xgb = XGBClassifier(
        n_estimators=200, max_depth=4, learning_rate=0.08,
        subsample=0.9, colsample_bytree=0.9,
        eval_metric="logloss", random_state=7,
    )
    xgb.fit(x_train, y_train)
    xgb_scores = xgb.predict_proba(x_test)[:, 1]

    # ---- evaluate ----
    report: dict = {"dataset_rows": len(frame), "k": K, "models": {}}
    for name, scores in (("logistic_regression", logreg_scores), ("xgboost", xgb_scores)):
        auc = roc_auc_score(y_test, scores)
        p_at_k, r_at_k = precision_recall_at_k(test, scores, K)
        report["models"][name] = {
            "auc": round(auc, 4),
            f"precision@{K}": round(p_at_k, 4),
            f"recall@{K}": round(r_at_k, 4),
        }
        print(f"{name:>20}:  AUC {auc:.3f}   P@{K} {p_at_k:.3f}   R@{K} {r_at_k:.3f}")

    # Baseline for honesty: rank by protein density alone.
    baseline = x_test["protein_per_100kcal"].to_numpy()
    p_base, r_base = precision_recall_at_k(test, baseline, K)
    report["baseline_protein_only"] = {f"precision@{K}": round(p_base, 4), f"recall@{K}": round(r_base, 4)}
    print(f"{'protein-only baseline':>20}:  P@{K} {p_base:.3f}   R@{K} {r_base:.3f}")

    # ---- readable coefficients ----
    coefs = pd.Series(
        logreg.named_steps["model"].coef_[0], index=FEATURE_COLUMNS
    ).sort_values()
    print("\nlogistic regression coefficients (standardized):")
    print(coefs.to_string(float_format="%+.3f"))

    # ---- persist the winner ----
    winner_name, winner = max(
        (("logistic_regression", logreg), ("xgboost", xgb)),
        key=lambda pair: report["models"][pair[0]]["auc"],
    )
    ARTIFACTS.mkdir(exist_ok=True)
    snapshot = Path(__file__).resolve().parent.parent / "data" / "processed"
    snapshot.mkdir(parents=True, exist_ok=True)
    frame[FEATURE_COLUMNS + ["label", "user_id"]].to_csv(
        snapshot / "features.csv", index=False
    )
    print(f"wrote feature table -> {snapshot / 'features.csv'}")

    joblib.dump({"model": winner, "features": FEATURE_COLUMNS, "name": winner_name},
                ARTIFACTS / "ranker.joblib")
    (ARTIFACTS / "metrics.json").write_text(json.dumps(report, indent=2))
    report["saved"] = winner_name
    print(f"\nsaved {winner_name} -> {ARTIFACTS / 'ranker.joblib'}")


if __name__ == "__main__":
    main()
