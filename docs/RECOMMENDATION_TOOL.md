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

- This is the pre-match workflow. The separate MCP tool `predict_live_match_bet(fixture_id)` uses current score, elapsed time, live shots, red cards and live market prices to estimate probabilities for the final result.
- Supported price extraction currently covers 1X2, Over/Under 2.5 and BTTS only.
- API-Football may return no odds for a fixture or plan/league combination. In that case candidates remain visible without fabricated prices.
- Best price means the highest price among bookmakers returned by the API for that request, not a guarantee that the user can access or place that price.
- The Poisson rates now use league goal baselines and home/away scoring and conceding splits when available. This is still an experimental approximation: opponent quality is represented through season attack/defence rates, home advantage is a starting factor rather than a calibrated league parameter, and out-of-sample calibration is still required.
- The tool currently spends one additional API request for odds per match analysis, subject to the API's cache and daily quota.

## Example invocation

Call `predict_match_bet(fixture_id=123456)` from the MCP client. The tool returns `primary_pick`, the complete `candidates` list, the best returned bookmaker price where available, and explicit model limitations.


## Coefficient preference

The candidate ranker now prefers decimal odds from **1.50 to 2.50** when candidates have the same recommendation status. This is a soft preference, not a probability claim and not a hard filter:
- Below 1.50: marked `LOW_ODDS`; still shown.
- 1.50–2.50: marked `PREFERRED`.
- Above 2.50: marked `HIGH_VARIANCE`; still shown and requires stronger scrutiny.

The status / EV assessment remains separate from the odds profile. A high coefficient alone never creates value. The primary recommendation first respects evidence status, then the preferred odds profile, then conservative EV and model probability. These default bands are configurable product policy to revisit after backtesting; they do not guarantee profitability.


## Bookmaker-consistent pricing and timestamps

The pre-match pricing layer calculates no-vig probabilities only from a complete
market quoted by one bookmaker. It does not combine a home price from one book,
a draw price from another and an away price from a third to estimate market
probabilities.

For each complete supported market:
- raw implied probability is 1 / decimal odds;
- overround is the sum of the bookmaker's raw implied probabilities minus 1;
- no-vig probability is that selection's raw implied probability divided by
  the sum for all outcomes from the same bookmaker;
- edge is model probability minus that no-vig market probability;
- point-estimate EV remains model probability multiplied by the selected
  decimal price, minus 1 (for the supported markets without push settlement).

The best available selection price can still be shown when its bookmaker market
is incomplete. In that case no-vig probability, overround and edge are null;
the system does not synthesize a market from other bookmakers.

Each quoted price retains:
- provider_updated_at: API-Football's fixture update timestamp for the odds feed;
- odds_observed_at: UTC time the upstream API response was received;
- odds_source and bookmaker.

The API response retrieval timestamp is retained with cached responses, so a
cache read does not masquerade as a fresh upstream observation. Neither
timestamp proves the bookmaker accepted a wager at that price.

The experimental model remains unvalidated. These pricing metrics do not
promote a candidate to VALUE_BET.


## Model v3 inputs

The forecast layer now uses the model's time-decayed, opponent-adjusted recent
form when available. Home-only and away-only recent samples are used when at
least three matches are present; otherwise the full recent sample is used.
For live prematch analysis, opponent strength is proxied by current season
standings. For historical walk-forward evaluation, opponent indices are
reconstructed exclusively from prior results and shrunk toward neutral.

These adjustments improve feature construction but do not constitute model
calibration or proof of betting profitability. The independent-Poisson
probabilities remain experimental and VALUE_BET remains disabled.
