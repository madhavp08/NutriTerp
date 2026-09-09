# Decisions

Short record of choices so the project stays easy to learn. Newer items go at the top.

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
