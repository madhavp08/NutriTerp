"""Pure HTML -> data parsing. No network, no database.

Keeping parsing separate means it can be unit-tested against saved HTML
files, and a site redesign only breaks this one file.
"""

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

# Menu page panes: pane-1/2/3 are breakfast/lunch/dinner.
PANE_TO_MEAL = {"pane-1": "breakfast", "pane-2": "lunch", "pane-3": "dinner"}

# Legend icon filename fragment -> our flag name.
# Icon files look like: /LegendImages/icons_2016_vegan.gif
ICON_TO_FLAG = {
    "vegan": "vegan",
    "vegetarian": "vegetarian",
    "halalfriendly": "halal_friendly",
    "local": "local",
    "dairy": "dairy",
    "egg": "egg",
    "fish": "fish",
    "shellfish": "shellfish",
    "gluten": "gluten",
    "soy": "soy",
    "sesame": "sesame",
    "nuts": "nuts",
    "coconut": "coconut",
    "pork": "pork",
    "alcohol": "alcohol",
    "pea_protein": "pea_protein",
}


@dataclass
class ParsedOffering:
    meal: str
    station: str
    recipe_id: str  # RecNumAndPort, e.g. "060062*2"
    name: str
    flags: set[str] = field(default_factory=set)


@dataclass
class ParsedLabel:
    serving_size: str | None = None
    calories: float | None = None
    protein_g: float | None = None
    total_fat_g: float | None = None
    saturated_fat_g: float | None = None
    trans_fat_g: float | None = None
    carbs_g: float | None = None
    fiber_g: float | None = None
    sugars_g: float | None = None
    added_sugars_g: float | None = None
    cholesterol_mg: float | None = None
    sodium_mg: float | None = None
    ingredients: str | None = None
    allergens: str | None = None


def parse_menu_page(html: str) -> list[ParsedOffering]:
    """Parse one hall/date menu page into offerings.

    Structure: each meal lives in a tab pane; inside a pane each station is a
    Bootstrap card with an h3.card-title and rows of a.menu-item-name links.
    """
    soup = BeautifulSoup(html, "lxml")
    offerings: list[ParsedOffering] = []

    for pane_id, meal in PANE_TO_MEAL.items():
        pane = soup.find(id=pane_id)
        if pane is None:
            continue
        for card in pane.find_all("div", class_="card"):
            title = card.find("h3", class_="card-title")
            if title is None:
                continue
            station = title.get_text(strip=True)
            # The first card of a pane is titled with the meal itself.
            if station.lower() == meal:
                station = "General"
            for row in card.find_all("div", class_="menu-item-row"):
                link = row.find("a", class_="menu-item-name")
                if link is None:
                    continue
                recipe_id = _recipe_id_from_href(link.get("href", ""))
                if recipe_id is None:
                    continue
                flags = set()
                for icon in row.find_all("img", class_="nutri-icon"):
                    flag = _flag_from_icon(icon.get("src", ""))
                    if flag:
                        flags.add(flag)
                offerings.append(
                    ParsedOffering(
                        meal=meal,
                        station=station,
                        recipe_id=recipe_id,
                        name=link.get_text(strip=True),
                        flags=flags,
                    )
                )
    return offerings


def parse_label_page(html: str) -> ParsedLabel:
    """Parse a label.aspx nutrition-facts page.

    The label markup is messy nested tables, so we flatten to text and use
    anchored regexes on well-known phrases like "Total Fat 12.2g".
    """
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)

    def grams(pattern: str) -> float | None:
        m = re.search(pattern + r"\s*(\d+(?:\.\d+)?)\s*g\b", text, re.IGNORECASE)
        return float(m.group(1)) if m else None

    def milligrams(pattern: str) -> float | None:
        m = re.search(pattern + r"\s*(\d+(?:\.\d+)?)\s*mg\b", text, re.IGNORECASE)
        return float(m.group(1)) if m else None

    label = ParsedLabel(
        total_fat_g=grams(r"Total Fat"),
        saturated_fat_g=grams(r"Saturated Fat"),
        trans_fat_g=grams(r"Trans\s*Fat"),
        carbs_g=grams(r"Total Carbohydrate\.?"),
        fiber_g=grams(r"Dietary Fiber"),
        sugars_g=grams(r"Total Sugars"),
        added_sugars_g=grams(r"Includes"),
        protein_g=grams(r"Protein"),
        cholesterol_mg=milligrams(r"Cholesterol"),
        sodium_mg=milligrams(r"Sodium"),
    )

    m = re.search(r"Calories per serving\s*(\d+(?:\.\d+)?)", text, re.IGNORECASE)
    if m:
        label.calories = float(m.group(1))

    m = re.search(r"Serving size\s*(.+?)\s*Calories", text, re.IGNORECASE)
    if m:
        label.serving_size = m.group(1).strip()

    m = re.search(r"INGREDIENTS:\s*(.+?)\s*(?:ALLERGENS:|The nutrient composition)", text)
    if m:
        label.ingredients = m.group(1).strip()

    m = re.search(r"ALLERGENS:\s*(.+?)\s*(?:The nutrient composition|$)", text)
    if m:
        label.allergens = m.group(1).strip()

    return label


def _recipe_id_from_href(href: str) -> str | None:
    m = re.search(r"RecNumAndPort=([^&'\"]+)", href)
    return m.group(1) if m else None


def _flag_from_icon(src: str) -> str | None:
    filename = src.lower().rsplit("/", 1)[-1]  # icons_2016_vegan.gif
    m = re.match(r"icons_\d+_(.+)\.(gif|png|jpg)", filename)
    if not m:
        return None
    return ICON_TO_FLAG.get(m.group(1))
