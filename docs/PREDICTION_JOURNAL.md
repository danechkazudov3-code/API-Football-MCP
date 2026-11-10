# Prediction journal

The prediction journal is an append-only record of pre-match forecast snapshots and candidate selections.

## What is recorded

- UTC time at which the scan was observed;
- fixture ID, kickoff, league/season and teams where supplied;
- data source and model version;
- model-validation flag;
- every market candidate, model probability, fair odds and status;
- initial bookmaker price when one is present;
- separate timestamped bookmaker price observations;
- eventual outcome and actual score when settled.

Every scan creates a new snapshot. A later scan does not overwrite an earlier forecast. This is necessary for auditability and for measuring price movement / CLV.

## MCP tools

- `get_prediction_journal_status()` — configuration and record counts.
- `list_prediction_journal(limit=50, fixture_id=None, status=None)` — recent candidate records.
- `add_prediction_odds(candidate_id, bookmaker, odds, source, captured_at, provider_updated_at)` — append a timestamped price observation. If `captured_at` is omitted, the server observation time is recorded.
- `settle_prediction_candidate(candidate_id, outcome, actual_score, settled_at)` — record `won`, `lost`, `push` or `void`.

The scanner automatically attempts to journal each analyzed fixture and returns a `journal` field explaining whether the write happened.

## Storage and production activation

The implementation uses SQLite (Python standard library). It is deliberately **disabled by default**. Set `PREDICTION_JOURNAL_DB_PATH` to enable it.

Do not point this variable at the normal Render container filesystem: the current Render web service uses the Free plan and has no persistent disk or managed database attached. Data stored on its ordinary filesystem can disappear after a restart or redeploy.

Before enabling production writes, attach a persistent storage solution and set the variable to a path on that persistent volume (for example, `/var/data/prediction_journal.sqlite3`). Alternatively, migrate the adapter to managed PostgreSQL. A configured path is reported as `PATH_CONFIGURED_NOT_VERIFIED`; the application cannot prove that the path is backed by durable storage.

The test suite uses temporary SQLite databases and verifies snapshot creation, odds observations and settlement without requiring an external service.

## Important limitations

- The first observed odds timestamp is the server's capture time, not necessarily the bookmaker's original quote timestamp. Provider update timestamps are stored separately when available.
- Manual odds entries should include the actual time they were observed and identify the bookmaker/source.
- No VALUE_BET status is enabled by journaling. The model remains unvalidated until separate out-of-sample testing passes.
- The journal stores snapshots; it does not yet calculate ROI, CLV, Brier score or Log Loss. Those are downstream analytics.
