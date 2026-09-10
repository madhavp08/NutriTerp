"""Cosine rerank math — no model download, no Postgres."""

from app.models import MenuItem
from app.recommend import Scored
from ml.rerank import blend, choose, cosine_similarities, minmax, taste_similarities


def test_minmax_stretches_and_handles_flat_lists():
    assert minmax([10, 20, 30]) == [0.0, 0.5, 1.0]
    assert minmax([4, 4, 4]) == [0.5, 0.5, 0.5]
    assert minmax([]) == []


def test_identical_vectors_have_cosine_one():
    assert cosine_similarities([1, 0], [[1, 0], [0, 1]]) == [1.0, 0.0]


def test_blend_is_weighted_average_of_normalized_rank_and_cosine():
    # ranks 0 and 10 -> minmax 0 and 1; cosines 1 and 0; weight 0.25
    # item A: 0.75*0 + 0.25*1 = 0.25
    # item B: 0.75*1 + 0.25*0 = 0.75
    assert blend([0, 10], [1.0, 0.0], weight=0.25) == [0.25, 0.75]


def test_taste_similarities_uses_injected_encoder():
    def encode(texts):
        # "donut" aligns with the query; "eggs" is orthogonal
        table = {"sweet donut": [1, 0], "Frosted Donut": [1, 0], "Scrambled Eggs": [0, 1]}
        return [table[t] for t in texts]

    sims = taste_similarities("sweet donut", ["Frosted Donut", "Scrambled Eggs"], encode=encode)
    assert sims[0] == 1.0
    assert sims[1] == 0.0


def test_choose_without_note_keeps_highest_ranker_score():
    eggs = MenuItem(id=1, recipe_id="e", name="Scrambled Eggs")
    donut = MenuItem(id=2, recipe_id="d", name="Frosted Donut")
    candidates = [
        (Scored(score=3.0, reasons=["protein"]), None, eggs),
        (Scored(score=0.5, reasons=[]), None, donut),
    ]
    picked = choose(candidates, already=set(), note=None)
    assert picked[2].name == "Scrambled Eggs"


def test_choose_taste_note_can_flip_a_close_call():
    # Rerank is a nudge (25% cosine). It can swap close 1st/2nd, not a
    # last-place junk item over a clear heuristic winner.
    eggs = MenuItem(id=1, recipe_id="e", name="Scrambled Eggs")
    teriyaki = MenuItem(id=2, recipe_id="t", name="Teriyaki Chicken")
    donut = MenuItem(id=3, recipe_id="d", name="Frosted Donut")
    candidates = [
        (Scored(score=3.0, reasons=["protein"]), None, eggs),
        (Scored(score=2.8, reasons=["protein"]), None, teriyaki),
        (Scored(score=0.5, reasons=[]), None, donut),
    ]

    def encode(texts):
        table = {
            "spicy asian food": [1, 0],
            "Teriyaki Chicken": [1, 0],
            "Scrambled Eggs": [0, 1],
            "Frosted Donut": [0, 1],
        }
        return [table[t] for t in texts]

    picked = choose(candidates, already=set(), note="spicy asian food", encode=encode)
    assert picked[2].name == "Teriyaki Chicken"
    assert "matches your tastes" in picked[0].reasons


def test_choose_skips_already_suggested_ids():
    a = MenuItem(id=1, recipe_id="a", name="A")
    b = MenuItem(id=2, recipe_id="b", name="B")
    candidates = [
        (Scored(score=2.0, reasons=[]), None, a),
        (Scored(score=1.0, reasons=[]), None, b),
    ]
    picked = choose(candidates, already={1}, note=None)
    assert picked[2].name == "B"
