# Backtesting and live model

## Walk-forward backtesting

MCP tool: `backtest_league(league_id, season, from_date, to_date, min_history=5)`.

- Fetches completed league fixtures for a bounded date range (maximum 180 days).
- Sorts fixtures chronologically.
- Predicts each fixture using only earlier completed fixtures for the same teams and league.
- Updates team and league history only after each prediction.
- Reports 1X2 Brier score, 1X2 log loss, 1X2 accuracy and Over 2.5 Brier score.
- Does not calculate ROI/yield because the ordinary fixtures endpoint does not provide historical bookmaker odds snapshots.

The initial backtest uses the same experimental Poisson family with recent-form shrinkage and league baseline. It is a probability-quality diagnostic, not proof of profitability. A later stage must compare the model to market closing prices and simple baselines on a separate chronological test period.

## Live model

MCP tool: `predict_live_match_bet(fixture_id)`.

Inputs:
- current match score and elapsed minute;
- prematch expected-goal baseline;
- live total shots and shots on target;
- red-card events;
- live odds returned by API-Football.

The model scales scoring intensities to remaining match time, applies bounded live-pressure adjustments and red-card effects, then calculates final-match 1X2, Over/Under 2.5 and BTTS probabilities from the remaining-goals score matrix.

The live model is separate from the prematch forecast. It does not treat the full-match prematch probabilities as if the match were still at 0-0 and minute 0.

## Known limitations

- Live pressure multipliers are heuristic and require historical in-play calibration.
- Stoppage-time and extra-time handling is approximate; penalty shootouts are not modelled.
- API-Football may omit live stats or odds for a fixture. Missing data must remain visible.
- Historical backtest profitability is not reported without timestamped historical odds.
- Both models remain unvalidated; neither can produce VALUE_BET until out-of-sample validation and uncertainty estimates pass configured thresholds.
