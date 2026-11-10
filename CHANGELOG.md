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

## 2026-11-10 — Static source-code audit
- Reviewed the prematch evaluator, odds extraction, analyzer, scanner, Poisson model, live model/workflow, backtest, journal, providers, and tool imports on feature/prediction-engine.
- Confirmed that current evaluator uses raw implied probability (1 / odds) and point-estimate EV (p * odds - 1); no no-vig calculation or explicit Edge calculation is present in this path.
- Confirmed that odds extraction keeps the best price per selection across bookmakers and drops provider quote timestamps.
- Confirmed that the live model is a separate heuristic remaining-time Poisson model using shots, shots on target, red cards and elapsed time; it is unvalidated and not historically backtested.
- Confirmed scanner attempts journal recording, but no path configured means recorded: 0; journal remains disabled.
- Read relevant tests but did not execute them. Render live state and the 53-tool live inventory were not re-verified.
- No application code or Render configuration was changed.
## 2026-11-10 — Render deployment rechecked
- Confirmed Render service is not suspended and remains on Free plan with auto-deploy from feature/prediction-engine.
- Latest listed deployment is live: dep-dbp38cjnv7mc73bbnue0, commit 6dbbf87a06603610a9829414666304e925c42197.
- Documentation branch remains separate from the Render deployment branch; no production code or Render settings were changed.