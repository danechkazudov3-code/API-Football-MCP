"""Tests for automatic upcoming fixture scanning."""
import pytest

from tools.scanner import scan_best_bets


@pytest.mark.asyncio
async def test_scan_ranks_fixture_recommendations_without_hiding_no_bet(monkeypatch):
    import tools.scanner as scanner

    async def fake_api(_endpoint, _params):
        return {
            "success": True, "rate_limit_remaining": 90,
            "data": [
                {"fixture": {"id": 11, "date": "2026-11-10T12:00:00+00:00",
                             "status": {"short": "NS"}}, "league": {"id": 39},
                 "teams": {"home": {"name": "A"}, "away": {"name": "B"}}},
                {"fixture": {"id": 12, "date": "2026-11-10T13:00:00+00:00",
                             "status": {"short": "NS"}}, "league": {"id": 39},
                 "teams": {"home": {"name": "C"}, "away": {"name": "D"}}},
                {"fixture": {"id": 13, "date": "2026-11-10T14:00:00+00:00",
                             "status": {"short": "FT"}}, "league": {"id": 39}},
            ],
        }

    async def fake_predict(fixture_id):
        status = "LEAN" if fixture_id == 11 else "NO_BET"
        return {
            "success": True, "status": status, "odds_available": True,
            "primary_pick": {
                "status": status, "odds_profile": "PREFERRED",
                "expected_value": 0.08 if fixture_id == 11 else -0.02,
                "model_probability": 0.54,
            },
            "candidates": [{"selection": "Home win"}],
            "match_analysis": {"recent_form": {"home": {"form": "WWDLW"}}},
        }

    monkeypatch.setattr(scanner, "api_request", fake_api)
    monkeypatch.setattr(scanner, "predict_match_bet", fake_predict)
    result = await scan_best_bets(scan_date="2026-11-10", max_fixtures=5)

    assert result["success"] is True
    assert result["fixtures_found"] == 2
    assert result["fixtures_analyzed"] == 2
    assert len(result["all_matches"]) == 2
    assert result["best_opportunity"]["fixture"]["id"] == 11
    assert result["best_opportunity"]["match_analysis"]["recent_form"]["home"]["form"] == "WWDLW"
    assert result["ranked_opportunities"][1]["status"] == "NO_BET"


@pytest.mark.asyncio
async def test_scan_validates_limits_before_api_call(monkeypatch):
    import tools.scanner as scanner

    async def fail_if_called(*_args, **_kwargs):
        raise AssertionError("API must not be called for invalid scan limits.")

    monkeypatch.setattr(scanner, "api_request", fail_if_called)
    result = await scan_best_bets(days_ahead=8)
    assert result["success"] is False
    assert "days_ahead" in result["error"]


@pytest.mark.asyncio
async def test_scan_stops_when_remaining_quota_is_critical(monkeypatch):
    import tools.scanner as scanner

    async def fake_api(_endpoint, _params):
        return {
            "success": True, "rate_limit_remaining": 3,
            "data": [
                {"fixture": {"id": i, "date": f"2026-11-10T{10+i}:00:00+00:00",
                             "status": {"short": "NS"}}}
                for i in range(1, 5)
            ],
        }

    calls = []

    async def fake_predict(fixture_id):
        calls.append(fixture_id)
        return {
            "success": True, "rate_limit_remaining": 2,
            "primary_pick": {"status": "INSUFFICIENT_DATA"},
            "candidates": [],
        }

    monkeypatch.setattr(scanner, "api_request", fake_api)
    monkeypatch.setattr(scanner, "predict_match_bet", fake_predict)
    result = await scan_best_bets(scan_date="2026-11-10")
    assert len(calls) == 1
    assert result["fixtures_analyzed"] == 1



@pytest.mark.asyncio
async def test_scan_returns_api_error_and_quota_without_unbound_variable(monkeypatch):
    import tools.scanner as scanner

    async def fake_api(_endpoint, _params):
        return {
            "success": False,
            "error": "API key rejected",
            "rate_limit_remaining": 77,
            "data": [],
        }

    monkeypatch.setattr(scanner, "api_request", fake_api)
    result = await scan_best_bets(scan_date="2026-11-10")

    assert result["success"] is False
    assert result["stage"] == "fixture_discovery"
    assert result["error"] == "API key rejected"
    assert result["rate_limit_remaining"] == 77


@pytest.mark.asyncio
async def test_scan_reports_latest_remaining_quota(monkeypatch):
    import tools.scanner as scanner

    async def fake_api(_endpoint, _params):
        return {
            "success": True, "rate_limit_remaining": 90,
            "data": [
                {"fixture": {"id": 21, "date": "2026-11-10T12:00:00+00:00",
                             "status": {"short": "NS"}}},
            ],
        }

    async def fake_predict(_fixture_id):
        return {
            "success": True, "rate_limit_remaining": 64,
            "primary_pick": {"status": "NO_BET", "odds_profile": "PREFERRED"},
            "candidates": [],
        }

    monkeypatch.setattr(scanner, "api_request", fake_api)
    monkeypatch.setattr(scanner, "predict_match_bet", fake_predict)
    result = await scan_best_bets(scan_date="2026-11-10")

    assert result["rate_limit_remaining"] == 64
