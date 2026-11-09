# MyAnalytics Football Advanced — Changelog

This is a curated project decision/change log, not a complete Git commit history.

## 2026-11-10 — Project state documentation started
- Created a separate documentation branch: `docs/project-state`, based on `feature/prediction-engine`.
- Added `PROJECT_STATE.md` to consolidate architecture, providers, limitations, validation status, infrastructure, and decisions.
- Added `ROADMAP.md` to make the next work items explicit.
- Added this `CHANGELOG.md`.
- No application code, Render environment variables, persistent storage, or production branch was changed.

## Earlier work — summarized from project history
- Added Football-Data.co.uk historical CSV provider and date parsing.
- Added Open-Matchday fallback provider for five major European club leagues.
- Updated scanner to use the fallback when API-Football data is unavailable or insufficient.
- Added experimental Poisson forecast from recent form and score-matrix market probabilities.
- Added tests for scanner and Open-Matchday behavior.
- Added SQLite prediction-journal implementation and four journal MCP tools.
- Journal remains disabled because durable storage is not configured; user deferred paid storage.
- Initial chronological walk-forward probability-quality evaluation was run; it did not evaluate profitability and did not validate the model.

For exact code changes, commits, and test runs, consult Git history and GitHub Actions. Do not infer missing dates or commit IDs from this summary.
