# MyAnalytics Football Advanced — Roadmap

The roadmap is ordered by dependency and current project constraints. Items are proposals until implemented and tested.

## Current phase — Establish reliable, auditable analysis

### P0 — Verify existing behavior before extending it
- [ ] Inventory actual MCP tool names and compare them with server registrations; Claude reported 53, but a live independent count is still outstanding.
- [ ] Verify current deployed commit and latest Render deploy status.
- [ ] Run focused tests for the current scanner, fallback provider, pricing evaluator and live model.
- [ ] Confirm report fields and status labels are consistent across fallback and API-Football paths.
- [x] Inspect current prematch pricing and odds extraction code; static review completed 2026-11-10.

### P1 — Improve market probability handling
- [x] Implement and test no-vig market probabilities for complete supported 1X2, Over/Under 2.5 and BTTS markets, keeping bookmakers separate (draft PR #2; not merged).
- [x] Calculate Edge explicitly as model probability minus same-bookmaker no-vig probability (draft PR #2; not merged).
- [x] Preserve bookmaker identity, provider update timestamp and separate upstream response retrieval timestamp; incomplete markets keep no-vig/Edge unavailable (draft PR #2; not merged).
- [x] Ensure overround/no-vig calculations never combine prices from different bookmakers (draft PR #2; not merged).
- [ ] Extend EV settlement logic before adding push/half-win/half-loss markets such as Asian lines.
- [ ] Do not enable VALUE BET status merely because no-vig and EV calculations exist.

### P2 — Evaluate model quality
- [ ] Establish a reproducible chronological walk-forward evaluation protocol.
- [ ] Compare model probabilities against simple baselines and market probabilities where valid odds exist.
- [ ] Track Brier score, log loss, calibration, sample size, and market coverage.
- [ ] Avoid leakage: only information available before kickoff may enter a forecast.
- [ ] Set explicit minimum sample sizes and acceptance thresholds before claiming validation.
- [ ] Evaluate ROI / CLV only when reliable timestamped odds are available.
- [ ] Build a separate historical evaluation dataset and validation protocol for live probabilities before treating live outputs as actionable.

### P3 — Improve data quality only when it unlocks a defined use case
- [ ] Audit Open-Matchday source rows when a concrete fixture appears anomalous.
- [ ] Measure coverage of shots, shots on target, corners, fouls, and cards; preserve missing values.
- [ ] Investigate additional free data providers only when current data blocks a specific required analysis.
- [ ] Do not add a national-team provider unless international-match analysis becomes a priority.

## Deferred
- [ ] Durable prediction journal: deferred until the user approves paid persistent storage or an acceptable free durable alternative is verified.
- [ ] Asian handicap / Asian total markets: deferred until settlement-aware probability and EV logic is implemented and tested.
- [ ] Accumulators / SGP: deferred until dependence modelling is justified and validated.
- [ ] Automatic Google Sheets workflow: deferred; connector availability alone does not establish a reliable journal pipeline.

## Definition of done for every task
A task is complete only when:
1. The code or configuration change is identified.
2. Relevant automated tests pass.
3. The deployed service is verified when deployment is required.
4. The actual MCP behavior is checked when a tool is involved.
5. Documentation is updated with the observed result and remaining limitations.

## Working rule
Work on one priority at a time. Do not start a lower-priority feature while a higher-priority correctness or validation issue remains unresolved, unless the user explicitly changes priorities.