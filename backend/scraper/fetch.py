"""Polite HTTP fetching for nutrition.umd.edu.

One shared client, a small delay between requests, and up to 3 attempts
per URL. Reliability rule: a scrape should fail loudly, never write
half-parsed garbage.
"""

import time

import httpx

BASE_URL = "https://nutrition.umd.edu"
DELAY_SECONDS = 0.5  # be gentle: ~2 requests/second max
ATTEMPTS = 3

_client = httpx.Client(
    timeout=30,
    headers={"User-Agent": "NutriTerp menu scraper (student project)"},
    follow_redirects=True,
)


def get(path: str, params: dict | None = None) -> str:
    """GET a page, retrying transient failures, returning HTML text."""
    last_error: Exception | None = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            response = _client.get(f"{BASE_URL}/{path.lstrip('/')}", params=params)
            response.raise_for_status()
            time.sleep(DELAY_SECONDS)
            return response.text
        except httpx.HTTPError as error:
            last_error = error
            time.sleep(2 * attempt)  # simple backoff: 2s, 4s
    raise RuntimeError(f"Failed to fetch {path} after {ATTEMPTS} attempts") from last_error


def fetch_menu_page(location_num: int, date) -> str:
    """Menu list page for one hall on one date."""
    dtdate = f"{date.month}/{date.day}/{date.year}"
    return get("/", {"locationNum": location_num, "dtdate": dtdate})


def fetch_label_page(recipe_id: str) -> str:
    """Nutrition facts page for one recipe (RecNumAndPort id)."""
    return get("label.aspx", {"RecNumAndPort": recipe_id})
