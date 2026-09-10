"""Scraper entry point.

    python -m scraper.run full    # scrape the next 7 days for all halls
    python -m scraper.run check   # daily: re-scrape only halls/dates whose menu changed

"full" runs weekly. "check" recomputes a cheap fingerprint from the menu
list pages (no label pages) and only does real work when it differs from
what the database remembers.
"""

import datetime
import hashlib
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Base, engine
from app.models import HALLS, MenuFingerprint, MenuItem, MenuOffering, ScrapeRun

from . import fetch, parse

DAYS_AHEAD = 7


def fingerprint(offerings: list[parse.ParsedOffering]) -> str:
    """Stable hash of what is served where. Ignores nutrition details."""
    lines = sorted(f"{o.meal}|{o.station}|{o.recipe_id}" for o in offerings)
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def upsert_hall_date(session: Session, hall_id: int, date: datetime.date,
                     offerings: list[parse.ParsedOffering]) -> int:
    """Replace one hall/date's offerings and fill in any missing nutrition.

    Label pages are only fetched for recipes we have never seen, so a full
    weekly scrape after the first one is mostly cheap list-page reads.
    """
    new_labels = 0
    for offering in offerings:
        item = session.scalar(select(MenuItem).where(MenuItem.recipe_id == offering.recipe_id))
        if item is None:
            label = parse.parse_label_page(fetch.fetch_label_page(offering.recipe_id))
            item = MenuItem(
                recipe_id=offering.recipe_id,
                name=offering.name,
                serving_size=label.serving_size,
                calories=label.calories,
                protein_g=label.protein_g,
                total_fat_g=label.total_fat_g,
                saturated_fat_g=label.saturated_fat_g,
                trans_fat_g=label.trans_fat_g,
                carbs_g=label.carbs_g,
                fiber_g=label.fiber_g,
                sugars_g=label.sugars_g,
                added_sugars_g=label.added_sugars_g,
                cholesterol_mg=label.cholesterol_mg,
                sodium_mg=label.sodium_mg,
                ingredients=label.ingredients,
                allergens=label.allergens,
            )
            session.add(item)
            session.flush()  # get item.id
            new_labels += 1
        # Diet flags come from the menu page and can change; always refresh.
        item.diet_flags = ",".join(sorted(offering.flags))

    # Replace the offering rows for this hall/date wholesale. Simpler than
    # diffing, and safe because offerings carry no user data.
    session.query(MenuOffering).filter_by(date=date, hall_id=hall_id).delete()
    items_by_recipe = {
        item.recipe_id: item
        for item in session.scalars(
            select(MenuItem).where(MenuItem.recipe_id.in_([o.recipe_id for o in offerings]))
        )
    }
    for offering in offerings:
        session.add(
            MenuOffering(
                date=date,
                hall_id=hall_id,
                meal=offering.meal,
                station=offering.station,
                menu_item_id=items_by_recipe[offering.recipe_id].id,
            )
        )

    stored = session.scalar(
        select(MenuFingerprint).where(
            MenuFingerprint.date == date, MenuFingerprint.hall_id == hall_id
        )
    )
    if stored is None:
        stored = MenuFingerprint(date=date, hall_id=hall_id, fingerprint="")
        session.add(stored)
    stored.fingerprint = fingerprint(offerings)
    return new_labels


def scrape(kind: str) -> None:
    Base.metadata.create_all(engine)
    today = datetime.date.today()
    dates = [today + datetime.timedelta(days=i) for i in range(DAYS_AHEAD)]

    with Session(engine) as session:
        run = ScrapeRun(kind=kind)
        session.add(run)
        session.commit()

        details: list[str] = []
        try:
            for hall_id, hall_name in HALLS.items():
                for date in dates:
                    offerings = parse.parse_menu_page(fetch.fetch_menu_page(hall_id, date))
                    if not offerings:
                        details.append(f"{hall_name} {date}: empty menu, skipped")
                        continue

                    if kind == "check":
                        stored = session.scalar(
                            select(MenuFingerprint).where(
                                MenuFingerprint.date == date,
                                MenuFingerprint.hall_id == hall_id,
                            )
                        )
                        if stored is not None and stored.fingerprint == fingerprint(offerings):
                            continue  # unchanged: no writes needed
                        details.append(f"{hall_name} {date}: menu changed, re-scraped")

                    new_labels = upsert_hall_date(session, hall_id, date, offerings)
                    session.commit()
                    details.append(
                        f"{hall_name} {date}: {len(offerings)} offerings, {new_labels} new labels"
                    )
            run.status = "ok"
        except Exception as error:  # noqa: BLE001 - record then re-raise
            session.rollback()
            run.status = "failed"
            details.append(f"ERROR: {error}")
            raise
        finally:
            run.detail = "\n".join(details) or "no changes"
            session.commit()
            print(f"[{kind}] {run.status}\n{run.detail}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    if mode not in ("full", "check"):
        sys.exit("usage: python -m scraper.run [full|check]")
    scrape(mode)
