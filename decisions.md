# Decisions

Short record of choices so the project stays easy to learn. Newer items go at the top.

## 2026-09-09 — Wait for constitution and answers

- `constitution.md` is intentionally blank. Real app work starts after you add rules there.
- Design questions are asked in chat before architecture is locked.

## 2026-09-09 — Ceremonial first commit

- First push was only `ganapthy.py` with `om ganapathaye nama:`.
- That file was deleted next so it is not part of the app.

## 2026-09-09 — Repo and process

- GitHub repo: https://github.com/madhavp08/NutriTerp
- After setup, each feature lands through its own pull request.
- Keep the ML stack understandable: logistic regression and XGBoost rankers, then a Sentence Transformer cosine rerank. No extra model families unless a later note says otherwise.
