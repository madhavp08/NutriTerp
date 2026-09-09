# NutriTerp

A UMD dining hall meal recommender. It scrapes the live menu from
[nutrition.umd.edu](https://nutrition.umd.edu/), stores it in Postgres, and ranks
meals for each user from their dietary rules, goals, and thumbs up / down feedback.

## Layout

```
backend/    FastAPI API, scraper, and ML code (Python)
frontend/   Next.js web app (login, questionnaire, daily suggestions)
constitution.md   Project rules (written by the owner)
decisions.md      Every design decision, short and readable
```

## Run it

1. Copy `.env.example` to `.env` and fill in `DATABASE_URL` (Neon Postgres) and `SESSION_SECRET`.
2. Backend:

   ```bash
   cd backend
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```

   Check http://localhost:8000/api/health — it should report the database as ok.
3. Frontend:

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

   Open http://localhost:3000.

## The ML, in one paragraph

Menu items become rows in Pandas with nutrition, cuisine, and dietary-flag
features. Hard filters remove anything that violates the user's allergies or
diet. A logistic regression (then XGBoost) ranks the rest using the user's
goals and past thumbs up / down. A Sentence Transformer embedding of the dish
name gives a cosine-similarity rerank toward dishes the user liked before.
Quality is measured offline with Precision@K and Recall@K.
