"""Database tables.

Three ideas, three tables:

- MenuItem: one row per recipe (identified by the site's RecNumAndPort id).
  Nutrition and diet flags live here because they belong to the recipe,
  not to the day it is served. This is the table ML features come from.
- MenuOffering: "recipe X is served at hall H, meal M, station S, on date D".
  One scrape produces many of these. This is what the recommender ranks.
- ScrapeRun: one row per scraper execution, with a per-hall/day fingerprint
  so the daily check can tell whether the menu changed without re-reading
  every nutrition label.
"""

import datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base

# The site's three halls, keyed by their locationNum query parameter.
HALLS = {16: "South Campus", 19: "Yahentamitsi", 51: "251 North"}

MEALS = ("breakfast", "lunch", "dinner")

# Legend icons on the menu page -> boolean flag columns on MenuItem.
# Kept as a simple list so adding an icon is a one-line change.
DIET_FLAGS = [
    "vegan",
    "vegetarian",
    "halal_friendly",
    "local",
    "dairy",
    "egg",
    "fish",
    "shellfish",
    "gluten",
    "soy",
    "sesame",
    "nuts",
    "coconut",
    "pork",
    "alcohol",
    "pea_protein",
]


class MenuItem(Base):
    __tablename__ = "menu_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))

    serving_size: Mapped[str | None] = mapped_column(String(64))
    calories: Mapped[float | None] = mapped_column(Float)
    protein_g: Mapped[float | None] = mapped_column(Float)
    total_fat_g: Mapped[float | None] = mapped_column(Float)
    saturated_fat_g: Mapped[float | None] = mapped_column(Float)
    trans_fat_g: Mapped[float | None] = mapped_column(Float)
    carbs_g: Mapped[float | None] = mapped_column(Float)
    fiber_g: Mapped[float | None] = mapped_column(Float)
    sugars_g: Mapped[float | None] = mapped_column(Float)
    added_sugars_g: Mapped[float | None] = mapped_column(Float)
    cholesterol_mg: Mapped[float | None] = mapped_column(Float)
    sodium_mg: Mapped[float | None] = mapped_column(Float)

    ingredients: Mapped[str | None] = mapped_column(Text)
    allergens: Mapped[str | None] = mapped_column(Text)

    # Comma-separated legend flags from DIET_FLAGS, e.g. "vegan,gluten".
    # One string column keeps the table readable when you SELECT * it;
    # code always goes through the flags property below.
    diet_flags: Mapped[str] = mapped_column(String(255), default="")

    scraped_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @property
    def flags(self) -> set[str]:
        return set(self.diet_flags.split(",")) if self.diet_flags else set()


class MenuOffering(Base):
    __tablename__ = "menu_offerings"
    __table_args__ = (
        UniqueConstraint("date", "hall_id", "meal", "station", "menu_item_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[datetime.date] = mapped_column(Date, index=True)
    hall_id: Mapped[int]  # locationNum: 16, 19, or 51
    meal: Mapped[str] = mapped_column(String(16))  # breakfast / lunch / dinner
    station: Mapped[str] = mapped_column(String(128))
    menu_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"), index=True)


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    kind: Mapped[str] = mapped_column(String(16))  # "full" or "check"
    status: Mapped[str] = mapped_column(String(16), default="running")  # running/ok/failed
    detail: Mapped[str | None] = mapped_column(Text)


class User(Base):
    """One account. Profile/questionnaire fields arrive in a later feature."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    # bcrypt hash, never the password itself. bcrypt strings are 60 chars.
    password_hash: Mapped[str] = mapped_column(String(72))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class UserSession(Base):
    """A logged-in browser. The cookie stores only the random token.

    Sessions live in the database (not a JWT) so logging out or deleting a
    row revokes access immediately, and there is no signing crypto to get
    wrong. The token is 64 hex chars from a CSPRNG - unguessable.
    """

    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MenuFingerprint(Base):
    """SHA-256 of the sorted offering list for one hall on one date.

    The daily check recomputes this from the (cheap) menu list pages and
    compares against the stored value; a mismatch triggers a re-scrape of
    just that hall/date.
    """

    __tablename__ = "menu_fingerprints"
    __table_args__ = (UniqueConstraint("date", "hall_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[datetime.date] = mapped_column(Date)
    hall_id: Mapped[int]
    fingerprint: Mapped[str] = mapped_column(String(64))
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
