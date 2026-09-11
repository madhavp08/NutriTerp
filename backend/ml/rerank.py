"""Second-stage cosine rerank with a small Sentence Transformer.

The ranker (heuristic or XGBoost) builds a shortlist. This module nudges
that shortlist toward dishes whose names sound like the user's free-text
taste_note ("spicy asian food, no mushrooms").

Cosine similarity is the angle between two embedding vectors:
1 means the same idea, 0 means unrelated. We min-max the ranker scores
on the shortlist first so a 4.2 heuristic and a 0.8 model probability
are comparable to a 0–1 cosine.

Embeddings are computed on the fly and kept in process memory. The MiniLM
model is ~80 MB; encoding a handful of names is milliseconds after load.
Persisting vectors in Postgres can wait until this is actually slow.
"""

import numpy as np

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
BLEND = 0.25  # share of the final score that comes from cosine
SHORTLIST = 8

_model = None


def get_model():
    """Load MiniLM once. None if the optional package is not installed."""
    global _model
    if _model is False:
        return None
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer(MODEL_NAME)
        except ImportError:
            _model = False
            return None
    return _model


def minmax(values: list[float]) -> list[float]:
    """Stretch a list onto [0, 1]. Flat lists become 0.5 (no information)."""
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.5] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


def cosine_similarities(query_vec, item_vecs) -> list[float]:
    query = np.asarray(query_vec, dtype=float)
    query = query / (np.linalg.norm(query) or 1.0)
    out = []
    for raw in item_vecs:
        item = np.asarray(raw, dtype=float)
        item = item / (np.linalg.norm(item) or 1.0)
        out.append(float(np.dot(query, item)))
    return out


def taste_similarities(note: str, texts: list[str], encode=None) -> list[float]:
    """Cosine(taste_note, each text). encode is injectable so tests stay offline."""
    if not note.strip() or not texts:
        return [0.0] * len(texts)
    if encode is None:
        model = get_model()
        if model is None:
            return [0.0] * len(texts)
        encode = lambda xs: model.encode(xs, normalize_embeddings=True)
    vectors = encode([note, *texts])
    return cosine_similarities(vectors[0], vectors[1:])


def blend(rank_scores: list[float], cosines: list[float], weight: float = BLEND) -> list[float]:
    """(1-weight) * minmax(rank) + weight * cosine, one value per candidate."""
    return [
        (1 - weight) * ranked + weight * cos
        for ranked, cos in zip(minmax(rank_scores), cosines)
    ]


def choose(candidates: list[tuple], already: set[int], note: str | None,
           encode=None) -> tuple | None:
    """Pick one (scored, offering, item) from a meal's eligible candidates.

    Prefer items not already suggested today. If the user wrote a taste_note,
    blend cosine similarity into the shortlist scores first.
    """
    if not candidates:
        return None
    fresh = [c for c in candidates if c[2].id not in already] or list(candidates)
    fresh.sort(key=lambda c: (c[0].score, c[2].name), reverse=True)
    short = fresh[:SHORTLIST]
    if note and note.strip():
        from app.recommend import Scored
        sims = taste_similarities(note, [c[2].name for c in short], encode=encode)
        finals = blend([c[0].score for c in short], sims)
        rescored = []
        for (scored, offering, item), sim, final in zip(short, sims, finals):
            reasons = list(scored.reasons)
            if sim >= 0.35:
                reasons.append("matches your tastes")
            rescored.append((Scored(score=final, reasons=reasons), offering, item))
        short = sorted(rescored, key=lambda c: (c[0].score, c[2].name), reverse=True)
    return short[0]
