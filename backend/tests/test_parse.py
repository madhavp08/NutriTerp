"""Parser tests against saved HTML.

menu_small.html is a trimmed copy of the real menu structure.
label_millet_chia_bun.html is a real, unmodified label.aspx download.
If UMD redesigns the site these tests break first — that is the point.
"""

from pathlib import Path

from scraper.parse import parse_label_page, parse_menu_page

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_menu_page_finds_all_offerings():
    offerings = parse_menu_page((FIXTURES / "menu_small.html").read_text())
    assert len(offerings) == 3

    by_name = {o.name: o for o in offerings}

    ham = by_name["Diced Ham"]
    assert ham.meal == "breakfast"
    assert ham.station == "General"  # first card is titled with the meal name
    assert ham.recipe_id == "060062*2"
    assert ham.flags == {"pork"}

    eggs = by_name["Scrambled Eggs"]
    assert eggs.station == "Chef's Table"
    assert eggs.flags == {"egg", "vegetarian"}

    buns = by_name["Millet & Chia Burger Buns"]
    assert buns.meal == "lunch"
    assert buns.station == "Salad Bar"
    assert buns.flags == {"vegan", "halal_friendly"}


def test_parse_real_label_page():
    label = parse_label_page((FIXTURES / "label_millet_chia_bun.html").read_text())

    assert label.calories == 264
    assert label.serving_size == "1 EACH"
    assert label.total_fat_g == 12.2
    assert label.saturated_fat_g == 0.9
    assert label.trans_fat_g == 0
    assert label.carbs_g == 34.9
    assert label.fiber_g == 4.7
    assert label.sugars_g == 0.9
    assert label.added_sugars_g == 0
    assert label.protein_g == 1.9
    assert label.cholesterol_mg == 0
    assert label.sodium_mg == 263.8
    assert "Little Northern Bakehouse" in label.ingredients
    assert "Pea Protein" in label.allergens


def test_empty_page_parses_to_nothing():
    assert parse_menu_page("<html><body></body></html>") == []
