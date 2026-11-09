# MyAnalytics Football Advanced — Project State

**Last reconciled:** 2026-11-10  
**Repository:** `danechkazudov3-code/API-Football-MCP`  
**Working branch:** `feature/prediction-engine`  
**Documentation branch:** `docs/project-state`  
**Purpose:** This file is the current handover note for future work. It is not proof that every listed behavior has been re-tested today.

## 1. Product goal

Build a football analytics system that analyzes specified matches and upcoming fixtures, estimates probabilities for supported markets, compares estimates with bookmaker prices, and declines to recommend bets when evidence is insufficient.

The project must distinguish:
- **Forecast:** model probability estimate.
- **LEAN / WATCHLIST:** an exploratory signal, not a betting recommendation.
- **NO BET / INSUFFICIENT DATA:** no actionable recommendation.
- **VALUE BET:** prohibited until the model has passed the project's calibration and validation requirements.

No profit or win-rate guarantees.

## 2. Current infrastructure

| Component | Known state |
|---|---|
| GitHub repository | `danechkazudov3-code/API-Football-MCP` |
| Main development branch | `feature/prediction-engine` |
| Documentation branch | `docs/project-state` (created for these documents; not merged) |
| Render service | `myanalytics-football-api` |
| Render service ID | `srv-dbottkjrjlhs73c9mkig` |
| Render URL | `https://myanalytics-football-api.onrender.com` |
| MCP endpoint | `https://myanalytics-football-api.onrender.com/mcp` |
| Render plan | Free, according to last inspected service state |
| Auto deploy | Enabled for `feature/prediction-engine`; documentation branch is separate |
| Claude MCP connector | Reconnected; Claude reported 53 tools on 2026-11-10 |
| Prediction journal storage | Disabled: durable storage is not configured |
| Render Postgres | No instance was present at last inspection |

Do not merge the documentation branch or change Render configuration without a reason. Do not add paid infrastructure without the user's explicit agreement.

## 3. Data providers and limitations

### API-Football
- The API key/account previously returned an account-suspended error through the project.
- The dashboard showed a Free plan with 100 requests/day and remaining quota, so quota exhaustion was not established as the cause.
- A direct dashboard test for La Liga 2026 returned a plan restriction: Free plan did not have access to that season (message suggested seasons 2022–2024).
- Treat API-Football availability as **unreliable / blocked pending a fresh successful test**. Do not claim every endpoint is unusable solely from the season restriction.

### Open-Matchday
- Implemented as a fallback provider for five club leagues: Premier League (39), La Liga (140), Serie A (135), Bundesliga (78), Ligue 1 (61).
- Uses daily CSV snapshots; not a live feed.
- Provides fixtures/results and recent-form aggregates from completed matches, including overall and home/away splits.
- Does not provide bookmaker odds, confirmed lineups, injuries, or live match data.
- Some match-stat fields (shots, shots on target, fouls, corners, cards) exist but are incomplete; missing values must not be treated as zero.
- The available fallback data is not a national-team data source. Do not assume it covers UEFA Nations League or other international fixtures.
- The La Liga provider reads a league-specific CSV path. Previous code review did not identify an explicit cross-league merge, but upstream data quality can still be checked when relevant.
- Respect the source's attribution and non-commercial-use conditions.

### Football-Data.co.uk
- Historical CSV source used for an initial probability-quality backtest.
- It is not a source for upcoming fixtures, lineups, injuries, live data, or timestamped odds history.
- Historical average closing odds do not establish timestamped CLV or a complete profitability evaluation.

## 4. Implemented code areas (known from prior project work)

These components were added or modified on `feature/prediction-engine`. Their current production state should be verified before relying on them.

- `tools/open_matchday_provider.py`: Open-Matchday CSV provider and recent-form extraction.
- `tools/scanner.py`: fixture scanning, API-Football to Open-Matchday fallback, fallback forecast formatting.
- `tools/poisson_model.py`: experimental Poisson goal-rate and score-matrix calculations.
- `tools/football_data_provider.py`: historical Football-Data.co.uk ingestion.
- `tools/prediction_journal.py`: SQLite-backed prediction-journal implementation.
- Tests include scanner, Open-Matchday provider, and related prediction paths.

### Forecast model
- Model identifier observed: `experimental_poisson_baseline_v2`.
- Uses recent scoring/conceding form with shrinkage and a home-advantage factor when richer league-normalized rates are unavailable.
- Generic prior previously observed: 1.35 goals; default home-advantage multiplier: 1.08.
- Builds a truncated Poisson score matrix (0–10) and derives 1X2, Over/Under 2.5, and BTTS probabilities.
- No confirmed calibration; `model_validated=false`.
- In fallback mode, league baseline may be unavailable and generic priors are used.
- Current fallback probabilities must be labelled experimental, not betting advice.

### Scanner
- Supports a bounded fixture scan (previously documented limits: 1–10 fixtures, 1–7 days).
- Falls back to Open-Matchday when API-Football fixture discovery or match analysis fails, subject to available fixtures.
- Without bookmaker prices, it must not create a primary pick or claim positive EV. Candidates are marked as insufficient data / no bet.
- A test for La Liga on 2026-11-20 found Athletic Club–Espanyol; it returned a probability-only forecast and no bet because odds were absent.

### Prediction journal
- Four MCP tools are exposed in Claude's reported tool list:
  - `get_prediction_journal_status`
  - `list_prediction_journal`
  - `add_prediction_odds`
  - `settle_prediction_candidate`
- Claude reported 53 total project connector tools after reconnecting on 2026-11-10; the four journal tools plausibly explain the increase from 49 to 53, but no before/after tool-list diff has been captured.
- Status was checked again on 2026-11-10 and returned:
  - `enabled: false`
  - `durability: NOT_CONFIGURED`
  - reason: set `PREDICTION_JOURNAL_DB_PATH` to a durable path because Render's default filesystem is ephemeral.
- Persistent Disk / Postgres is not configured. User explicitly deferred paid storage.
- Therefore do not claim that forecasts are being durably recorded. Do not repeatedly ask the user to re-run the same status check unless configuration has changed.

## 5. Validation status and known test results

### Current validation gate
- `model_validated=false`.
- No demonstrated profitability.
- No valid ROI/CLV evaluation from timestamped odds history.
- No calibrated uncertainty interval or validated `P(EV>0)` claim established.
- No VALUE BET recommendations until the project validation requirements are met.

### Historical backtest snapshot
A prior La Liga Football-Data.co.uk walk-forward run returned:
- 119 fixtures received; 68 evaluated after minimum-history filtering (minimum 5 prior matches).
- 1X2 Brier score: 0.6024604452.
- 1X2 log loss: 1.0117645410.
- 1X2 accuracy: 0.50.
- Over 2.5 Brier score: 0.2341212928.
- Odds coverage: 0; profitability not evaluated.
- Date range: 2026-07-01 to 2026-11-08.
This is an initial experimental baseline only. It does not establish that the model is better than the market or profitable.

### CI / deployment history (historical, not a live status check)
- GitHub Actions run `42697451266` was reported completed successfully.
- Render deploy `dep-dbp364g622ns738oi6qg`, commit `63118bc8a0650fa9a60ea74a782edc946e67a644`, was reported live.
- Re-check CI and deployment before relying on these as current state.

## 6. Decisions and constraints

- Do not buy Render Persistent Disk or Postgres unless the user explicitly changes the budget decision.
- Do not merge PR #1 or alter infrastructure without a clear need and user agreement.
- Keep prematch and live models separate.
- Prioritize bookmaker odds in the 1.50–2.50 range as a preference, not a hard exclusion.
- Odds must carry bookmaker and capture timestamp; untimestamped odds are unverified.
- Do not invent odds, lineups, injuries, xG, or missing statistics.
- Do not treat a fair-odds calculation as evidence that the underlying probability is accurate.
- Keep all available market candidates visible where practical; do not silently hide options through arbitrary filters.
- H2H is secondary evidence, not a substitute for current team strength and form.
- The user prefers focused analysis of a specified match over unnecessarily scanning large fixture sets.
- Avoid expanding the product surface until data quality and forecast evaluation improve.

## 7. How to maintain this file

After each meaningful project task:
1. Record the exact change and affected files/tools.
2. Record the test command or MCP call and its actual result.
3. Record deployment status separately from CI status.
4. Update the known limitations and next task.
5. Never mark a feature "working" based only on its name appearing in Claude's tool list.
6. If a fact was not rechecked, label it historical / not freshly verified.

This document is a handover aid, not a substitute for reading code, checking tests, and inspecting Render.
