# Automatic match recommendation tool

The MCP tool `predict_match_bet(fixture_id)` provides a first end-to-end pre-match candidate-selection path.

## Current behavior

1. Calls `analyze_match` to load the fixture, recent form and experimental Poisson market probabilities.
2. Makes one unfiltered pre-match `/odds` request for that fixture.
3. Reads the returned bookmakers without requiring a specific bookmaker.
4. Finds the best returned decimal price for supported selections:
   - Match Winner: Home / Draw / Away
   - Goals Over/Under: Over 2.5 / Under 2.5
   - Both Teams Score: Yes / No
5. Prices each model candidate, calculates fair odds and point-estimate expected value, assigns a status, and selects a primary candidate.
6. Returns all candidates. A candidate is not hidden because it is not VALUE_BET.

## Status safety

The current Poisson baseline is experimental, uses only a small recent-form sample, and is not calibrated or backtested. Consequently, `model_validated=False` is always passed to the pricing layer. Positive point-estimate EV can be labelled LEAN, but never VALUE_BET. Missing odds or probabilities produce INSUFFICIENT_DATA. This is intentional.

## Limitations / next work

- This is pre-match only. Live requires a separate in-play state model using score, elapsed time, red cards, live statistics and live market prices.
- Supported price extraction currently covers 1X2, Over/Under 2.5 and BTTS only.
- API-Football may return no odds for a fixture or plan/league combination. In that case candidates remain visible without fabricated prices.
- Best price means the highest price among bookmakers returned by the API for that request, not a guarantee that the user can access or place that price.
- The Poisson rates need league baselines, home advantage, opponent-strength adjustment, larger samples, and out-of-sample calibration/backtesting before any VALUE_BET status can be enabled.
- The tool currently spends one additional API request for odds per match analysis, subject to the API's cache and daily quota.

## Example invocation

Call `predict_match_bet(fixture_id=123456)` from the MCP client. The tool returns `primary_pick`, the complete `candidates` list, the best returned bookmaker price where available, and explicit model limitations.
