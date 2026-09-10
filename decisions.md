# Decisions

Short record of choices so the project stays easy to learn. Newer items go at the top.

## 2026-09-09 — PR 2 follow-up: empty-allergen parsing bug

- Items with no allergens render "ALLERGENS:" directly followed by the site's legal disclaimer. The regex used `.+?` (one or more), which cannot match an empty list, so it captured the whole disclaimer + footer into the allergens column (512 rows).
- Fix: `.*?` plus "keep None when the capture is empty". Same fix applied to ingredients, which had the identical latent bug. Regression test added with a synthetic empty-allergen label.
- Lesson: verify scraped output in the database, not just parser unit tests — the fixtures never contained an allergen-free item.

## 2026-09-09 — PR 2: Scraper and menu schema

- nutrition.umd.edu is a FoodPro site. One URL per hall/date (`/?locationNum=16|19|51&dtdate=M/D/YYYY`) lists all meals; each item links to `label.aspx?RecNumAndPort=...` with full nutrition facts, ingredients, and allergens. No JavaScript needed, so plain HTTP + BeautifulSoup is enough — no browser automation.
- Parsing lives in `scraper/parse.py` with zero network or DB code, so it is unit-testable against saved HTML. If UMD redesigns, only this file breaks, and the tests say so first.
- Four tables: `menu_items` (one row per recipe: nutrition + diet flags — the ML feature source), `menu_offerings` (recipe X at hall H, meal M, station S, date D — what gets ranked), `menu_fingerprints` (SHA-256 of a hall/day's offering list), `scrape_runs` (audit log of every run).
- Nutrition label pages are fetched only for recipes never seen before. Recipes repeat constantly, so after the first scrape a weekly run is mostly 21 cheap list pages.
- Daily "did it change?" check recomputes the fingerprint from list pages and re-scrapes only mismatched hall/dates. Weekly full scrape covers the next 7 days.
- Scheduling is GitHub Actions cron (Mon 10:00 UTC full, daily 11:00 UTC check) instead of laptop cron, because a laptop is often asleep. Needs the `DATABASE_URL` repo secret.
- Diet flags stored as one comma-separated string column instead of 16 boolean columns — easier to read in a SELECT, one line to extend, and code always goes through a `flags` set property.
- Politeness: 0.5s delay between requests, 3 attempts with backoff, honest User-Agent. A failed scrape fails loudly and is recorded in `scrape_runs` rather than half-writing.
- Tables are created with `Base.metadata.create_all` (no Alembic migrations yet) — fewer moving parts while the schema is young.

## 2026-09-09 — PR 1: Scaffold

- Two folders: `backend/` (FastAPI + Python ML) and `frontend/` (Next.js). One repo so one PR can touch both.
- Backend deps are pinned loosely in `requirements.txt`; a plain `venv` keeps setup obvious (no Poetry/uv to learn on top).
- `config.py` reads `.env` at the repo root with pydantic-settings, so backend and any scripts share one secrets file.
- SQLAlchemy 2 with the psycopg3 driver; `pool_pre_ping=True` because Neon suspends idle computes and stale connections must be detected.
- `/api/health` runs `SELECT 1` so "is the DB reachable" is a one-URL check.
- Database: Neon project `nutriterp` (aws-us-east-1). Secrets live only in `.env`, which is git-ignored; `.env.example` documents the shape.
- Each feature branch becomes a PR and is merged right after checks, so `main` always runs and the PR trail stays readable one feature at a time.

## 2026-09-09 — Locked product choices

- Auth: email + password (bcrypt hash in Postgres). No Google OAuth.
- Database: hosted Neon Postgres. App reads `DATABASE_URL`.
- Home screen: one breakfast, one lunch, one dinner. User cannot swap yet.
- Diet and allergen rules are hard filters: violating meals never appear.
- If the user gives optional body info, compute a daily calorie target with Mifflin-St Jeor, then adjust for lose / maintain / gain.
- Scrape all three halls: South Campus, Yahentamitsi, 251 North.

## 2026-09-09 — Defaults I will use unless you change them

- Explicit feedback is thumbs up / thumbs down. That becomes a simple 1 / 0 label for the rankers.
- Session is an HTTP-only cookie, not a token stored in JavaScript.
- Frontend is Next.js App Router. Backend is FastAPI.
- Features live in Pandas tables (nutrition, cuisine, diet flags, like/dislike counts) so you can inspect them as CSV.
- Ranker is logistic regression first (easy to inspect coefficients), then XGBoost. Sentence Transformer cosine similarity is a second-stage rerank only.
- Offline metrics are Precision@K and Recall@K with a small K (3 or 5).
- Full scrape weekly. A cheap menu fingerprint check runs daily; if it changes, scrape again.
- `gh` is not installed on this machine yet. I will install it before the first feature PR.

## 2026-09-09 — Wait for constitution

- `constitution.md` is still blank. App code starts after you add rules there and say to begin.

## 2026-09-09 — Ceremonial first commit

- First push was only `ganapthy.py` with `om ganapathaye nama:`.
- That file was deleted next so it is not part of the app.

## 2026-09-09 — Repo and process

- GitHub repo: https://github.com/madhavp08/NutriTerp
- After setup, each feature lands through its own pull request.
- Keep the ML stack understandable: logistic regression and XGBoost rankers, then a Sentence Transformer cosine rerank. No extra model families unless a later note says otherwise.
