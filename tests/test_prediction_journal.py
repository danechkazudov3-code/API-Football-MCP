import asyncio

from tools.prediction_journal import (
    add_prediction_odds,
    get_prediction_journal_status,
    list_prediction_journal,
    record_scan_reports,
    settle_prediction_candidate,
)


def _sample_report():
    return {
        "fixture": {
            "id": 12345,
            "date": "2026-11-20T19:00:00+00:00",
            "league": {"id": 140, "name": "La Liga", "season": 2026},
            "teams": {
                "home": {"name": "Athletic Club"},
                "away": {"name": "Espanyol"},
            },
        },
        "model": "experimental_poisson_baseline_v2",
        "model_validated": False,
        "candidates": [
            {
                "market": "1X2",
                "selection": "Home win",
                "model_probability": 0.52,
                "fair_odds": 1.923,
                "odds": 2.05,
                "bookmaker": "ExampleBook",
                "status": "LEAN",
            },
            {
                "market": "Total goals 2.5",
                "selection": "Under 2.5",
                "model_probability": 0.55,
                "fair_odds": 1.818,
                "odds": None,
                "status": "INSUFFICIENT_DATA",
            },
        ],
    }


def test_journal_is_explicitly_disabled_without_persistent_path(monkeypatch):
    monkeypatch.delenv("PREDICTION_JOURNAL_DB_PATH", raising=False)
    result = record_scan_reports([_sample_report()])
    assert result["enabled"] is False
    assert result["recorded"] == 0


def test_journal_records_immutable_snapshot_candidates_and_odds(tmp_path, monkeypatch):
    db_path = tmp_path / "journal.sqlite3"
    monkeypatch.setenv("PREDICTION_JOURNAL_DB_PATH", str(db_path))

    result = record_scan_reports([_sample_report()], data_source="test-provider")
    assert result["enabled"] is True
    assert result["recorded"] == 1

    status = asyncio.run(get_prediction_journal_status())
    assert status["snapshots"] == 1
    assert status["candidates"] == 2
    assert status["odds_observations"] == 1
    rows = asyncio.run(list_prediction_journal(limit=10))
    assert rows["success"] is True
    assert rows["count"] == 2

    priced = next(item for item in rows["items"] if item["selection"] == "Home win")
    assert priced["fixture_id"] == "12345"
    assert priced["home_team"] == "Athletic Club"
    assert priced["model_validated"] == 0
    assert priced["initial_odds"] == 2.05
    assert priced["bookmaker"] == "ExampleBook"

    unpriced = next(item for item in rows["items"] if item["selection"] == "Under 2.5")
    assert unpriced["initial_odds"] is None

    observation = asyncio.run(add_prediction_odds(
        candidate_id=unpriced["candidate_id"],
        bookmaker="PARI",
        odds=1.91,
        source="manual",
        captured_at="2026-11-09T20:00:00+00:00",
    ))
    assert observation["success"] is True

    settled = asyncio.run(settle_prediction_candidate(
        candidate_id=unpriced["candidate_id"],
        outcome="won",
        actual_score="0-0",
        settled_at="2026-11-20T21:00:00+00:00",
    ))
    assert settled["success"] is True

    refreshed = asyncio.run(list_prediction_journal(
        limit=10, status="INSUFFICIENT_DATA"
    ))
    item = next(x for x in refreshed["items"] if x["candidate_id"] == unpriced["candidate_id"])
    assert item["outcome"] == "won"
    assert item["actual_score"] == "0-0"


def test_journal_rejects_invalid_odds_and_outcomes(tmp_path, monkeypatch):
    monkeypatch.setenv("PREDICTION_JOURNAL_DB_PATH", str(tmp_path / "journal.sqlite3"))
    record_scan_reports([_sample_report()])
    rows = asyncio.run(list_prediction_journal(limit=10))
    candidate_id = rows["items"][0]["candidate_id"]

    bad_odds = asyncio.run(add_prediction_odds(candidate_id, "PARI", 1.0))
    assert bad_odds["success"] is False
    bad_outcome = asyncio.run(settle_prediction_candidate(candidate_id, "maybe"))
    assert bad_outcome["success"] is False
