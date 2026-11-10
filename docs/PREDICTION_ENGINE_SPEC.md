# MyAnalytics Football Advanced — Prediction Engine Specification

## 1. Product requirement

For every supported pre-match or live fixture, the system must independently select and present its best forecasted betting candidate. The user must not have to choose a market manually.

The system is an analytical decision-support tool. It does not place bets, guarantee outcomes, or treat a high decimal price as evidence of value.

## 2. Candidate visibility is separate from recommendation

Do not use a strict value threshold as a display filter. Keep relevant candidates visible even when they are not recommended.

Every candidate must have fixture, market, selection, period and live match state where applicable; bookmaker, decimal odds, odds timestamp and source; model probability and uncertainty; fair odds when probability is available; implied probability with overround removed where possible; expected value when inputs are valid; status, reasons, missing evidence and conditions that would change the status.

If a probability is unavailable or unsupported, do not invent fair odds or EV. Mark those fields unavailable and explain why.

## 3. Status model

- VALUE_BET: validated model for this market/context, adequate data quality, and a conservative probability estimate clears the configured value threshold after uncertainty and market-margin handling.
- LEAN: candidate is supported, but edge, calibration, sample size or data quality is not strong enough for VALUE_BET.
- WATCHLIST: potentially interesting candidate; price, line, live state or additional evidence needs monitoring.
- NO_BET: candidate is evaluated and displayed, but current price/evidence does not justify recommending a wager.
- INSUFFICIENT_DATA: essential inputs are missing, stale or contradictory; no reliable probability claim is made.

NO_BET and INSUFFICIENT_DATA must never silently suppress a candidate. Show the best available candidate if identifiable, while clearly stating it is not a recommended bet. If no market data exists, show the best forecasted outcome separately from a priced betting candidate.

## 4. Automatic selection

1. Discover supported markets and available selections from the odds feed.
2. Generate probabilities only for markets supported by an implemented and validated model.
3. Normalize complete bookmaker markets to account for overround where possible.
4. Compare candidates using conservative expected value, uncertainty, data freshness, market coverage and model validation.
5. Select one primary candidate, even if LEAN, WATCHLIST or NO_BET, provided enough information exists to identify it.
6. Show ranked alternatives and explain why the primary candidate ranks highest.
7. Never rank candidates using raw odds alone. High odds are not inherently valuable.

When no reliable probability is available, show a qualitative forecast/watchlist candidate if possible, but do not label it VALUE_BET or fabricate EV.

## 5. Price and probability thresholds

For decimal odds O and estimated probability p:
- raw implied probability = 1 / O;
- for a complete bookmaker market, no-vig probability = (1 / O_selection) / Σ(1 / O_outcome) using outcomes from that same bookmaker only;
- edge = model probability − no-vig market probability;
- fair odds = 1 / p;
- expected value per unit stake = p * O - 1;
- break-even probability = 1 / O.

For configured target expected return r, minimum price at probability p is (1 + r) / p. Minimum probability at price O is (1 + r) / O.

Thresholds must be configuration, not hard-coded assumptions. Once uncertainty estimation exists, VALUE_BET must use a conservative lower probability bound. If uncertainty is unavailable or calibration has not passed validation, downgrade the status.

## 6. Model development sequence

Do not implement a pretend predictive model. Build and validate in stages.

### Stage A — data and candidate layer
- Fixture state, teams, league, season, kickoff and venue.
- Recent results with home/away split and opponent strength where available.
- Team statistics, goals for/against, xG if available, lineups, injuries/suspensions and rest days where coverage permits.
- Pre-match and live odds from all available bookmakers, retaining provider identity and timestamps.
- Explicit missing-data and stale-data indicators.

### Stage B — baseline probability model
- Start with a transparent Poisson goals baseline, estimating home and away scoring intensities from relevant attack/defence rates, league baseline and home advantage.
- Produce a scoreline probability matrix.
- Derive 1X2, totals, BTTS and supported handicap probabilities from that matrix.
- Keep unsupported markets unavailable rather than guessing.
- Consider Dixon-Coles low-score dependence only after baseline tests justify it.

### Stage C — calibration and validation
- Use chronological train/validation/test splits; never leak future results into features.
- Evaluate log loss, Brier score, calibration curves and market-specific performance.
- Compare against bookmaker-implied probabilities and simple league baselines.
- Track sample size, coverage and confidence intervals.
- Backtest with closing-line comparisons where reliable odds history exists; account for margin and realistic price availability.
- Do not promote a market to VALUE_BET until out-of-sample calibration and configured minimum sample criteria pass.

### Stage D — live model
- Recalculate from current score, elapsed time, red cards, substitutions and live statistics.
- Model remaining-time goals, not full-match probabilities as if the match had not started.
- Validate live-state freshness and reject stale or contradictory snapshots.
- Use live odds and live market IDs independently from pre-match bet IDs.
- If critical live inputs are stale or unavailable, return INSUFFICIENT_DATA.

## 7. Provider independence

- Do not hardwire the model to Bet365, PARI or any single bookmaker.
- Preserve all bookmakers returned by the live odds endpoint.
- For pre-match odds, allow configurable bookmaker selection and/or best available price across eligible bookmakers.
- Keep odds-provider adapters separate from probability modelling.
- Record bookmaker, market, selection, odds, timestamp and source for every price.
- Do not assume catalogue availability means odds exist for a specific fixture.

## 8. Response contract

The final match report must include fixture and mode (PREMATCH/LIVE); primary automatically selected candidate and status; market, selection, bookmaker, current odds and timestamp; model probability, uncertainty/confidence and fair odds only when supported; implied probability, EV and edge only when valid; selection rationale; price/probability needed for VALUE_BET; ranked alternatives and statuses; data quality and validation warnings; and a statement that forecasts are not guarantees.

For NO_BET, still display the best candidate and explain why it is not recommended. For INSUFFICIENT_DATA, do not manufacture a numeric forecast.

## 9. Current implementation boundary

The existing tools/analyzer.py collects fixture information and recent five-match form only. It explicitly states probability and betting-value calculations are not implemented. This specification does not change that fact.

The first implementation milestone is tested deterministic calculation modules and a stable output schema. Next comes the baseline probability model, followed by historical validation. The project must not claim a mathematically validated betting recommendation until those stages are complete.

## 8. Implemented pre-match model baseline — version 3

The current branch implements an opponent-adjusted, time-weighted independent
Poisson baseline. It is still experimental and is not approved for VALUE_BET.

Feature construction:
- Up to ten latest completed matches for each team.
- Prefer home-only recent history for the home side and away-only history for
  the away side when at least three venue-specific matches exist; otherwise use
  the larger all-venue sample.
- Exponentially decay match influence with a four-match half-life.
- For upcoming fixtures, adjust recent goals using opponent attack/defence
  indices derived from the current season standings. Opponent multipliers are
  bounded to 0.60–1.60; unknown opponents receive a neutral multiplier.
- When season venue rates and league baseline are available, blend those rates
  with adjusted recent form. The recent-form blend weight grows with sample
  size and is capped at 35%.
- If season aggregates are unavailable, shrink recent rates toward the league
  prior rather than trusting a small sample at full strength.
- Convert the two goal intensities into a normalized independent-Poisson score
  matrix, then derive supported 1X2, Over/Under 2.5 and BTTS probabilities.

Historical validation uses a separate leakage-safe feature path:
- Team histories, venue splits, league scoring baseline and opponent strength
  are built only from fixtures completed before the forecast date.
- Fixtures on the same calendar date are all forecast before any result from
  that date is added to history.
- Historical opponent indices are shrunk toward neutral according to sample
  size; the current standings snapshot is never used in walk-forward history.

Known limitations:
- Current standings are a present-time snapshot for live prematch analysis and
  must not be retroactively used to validate historical predictions.
- No xG, player-level lineup adjustment, rest/travel model or calibrated
  uncertainty interval is currently implemented.
- Home advantage, shrinkage and recent/season blend weights are provisional.
- Independent Poisson assumes conditional independence between team goals;
  Dixon-Coles or another low-score correction requires separate fitting.
- Backtest metrics remain probability-quality metrics only. No ROI/CLV claim is
  possible without reliable timestamped historical prices.
