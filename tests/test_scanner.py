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

    async def fake_fallback(*_args, **_kwargs):
        return {"success": False, "error": "Fallback unavailable", "source": "open-matchday"}

    monkeypatch.setattr(scanner, "api_request", fake_api)
    monkeypatch.setattr(scanner, "fetch_open_matchday_scan", fake_fallback)
    result = await scan_best_bets(scan_date="2026-11-10")

    assert result["success"] is False
    assert result["stage"] == "fixture_discovery"
    assert result["error"] == "API key rejected"
    assert result["fallback_error"] == "Fallback unavailable"
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


@pytest.mark.asyncio
async def test_scan_uses_open_matchday_when_api_fixtures_are_unavailable(monkeypatch):
    import tools.scanner as scanner

    async def fake_api(_endpoint, _params):
        return {"success": False, "error": "Free plan season restriction", "data": []}

    async def fake_fallback(league_id, start_date, end_date, max_fixtures):
        assert league_id == 140
        assert start_date == "2026-11-20"
        assert end_date == "2026-11-20"
        assert max_fixtures == 1
        form = {
            "available": True, "matches_played": 5,
            "average_goals_scored": 1.6, "average_goals_conceded": 1.0,
            "form": "WWDLW", "matches": [],
        }
        return {
            "success": True, "source": "open-matchday",
            "fixtures_found_in_window": 1,
            "fixtures": [{
                "fixture": {"id": "open-matchday:140:test", "teams": {"home_name": "A", "away_name": "B"}},
                "home_form": form, "away_form": form,
                "home_venue_form": form, "away_venue_form": form,
                "model_home_form": form, "model_away_form": form,
            }],
            "data_limitations": ["No odds"],
        }

    monkeypatch.setattr(scanner, "api_request", fake_api)
    monkeypatch.setattr(scanner, "fetch_open_matchday_scan", fake_fallback)
    result = await scan_best_bets(
        scan_date="2026-11-20", days_ahead=1, league_id=140, max_fixtures=1
    )

    assert result["success"] is True
    assert result["status"] == "FALLBACK_SCAN_COMPLETED"
    assert result["data_source"] == "open-matchday"
    assert result["fixtures_analyzed"] == 1
    assert result["best_opportunity"] is None
    assert result["all_matches"][0]["odds_available"] is False
    assert result["all_matches"][0]["forecast"]["available"] is True
    forecast = result["all_matches"][0]["forecast"]
    assert forecast["primary_forecast"]["status"] == "INSUFFICIENT_DATA"
    assert all(item["status"] == "INSUFFICIENT_DATA" for item in forecast["candidates"])
    assert all(item["status"] == "INSUFFICIENT_DATA" for item in result["all_matches"][0]["forecast_candidates"])


@pytest.mark.asyncio
async def test_scan_falls_back_when_api_fixture_analysis_fails(monkeypatch):
    import tools.scanner as scanner

    async def fake_api(_endpoint, _params):
        return {
            "success": True, "data": [
                {"fixture": {"id": 555, "date": "2026-11-20T21:00:00+00:00",
                             "status": {"short": "NS"}},
                 "league": {"id": 140},
                 "teams": {"home": {"name": "Athletic Club"}, "away": {"name": "Espanyol"}}}
            ],
        }

    async def fake_predict(_fixture_id):
        return {"success": False, "error": "Season access restricted"}

    async def fake_fallback(league_id, start_date, end_date, max_fixtures):
        assert league_id == 140
        form = {
            "available": True, "matches_played": 5,
            "average_goals_scored": 1.4, "average_goals_conceded": 1.1,
            "form": "WDLWW", "matches": [],
        }
        return {
            "success": True, "source": "open-matchday",
            "fixtures_found_in_window": 1,
            "fixtures": [{
                "fixture": {"id": "open-matchday:140:test"},
                "home_form": form, "away_form": form,
                "home_venue_form": form, "away_venue_form": form,
                "model_home_form": form, "model_away_form": form,
            }],
            "data_limitations": ["No odds"],
        }

    monkeypatch.setattr(scanner, "api_request", fake_api)
    monkeypatch.setattr(scanner, "predict_match_bet", fake_predict)
    monkeypatch.setattr(scanner, "fetch_open_matchday_scan", fake_fallback)
    result = await scan_best_bets(
        scan_date="2026-11-20", days_ahead=1, league_id=140, max_fixtures=1
    )

    assert result["success"] is True
    assert result["status"] == "FALLBACK_SCAN_COMPLETED"
    assert result["all_matches"][0]["fixture"]["id"] == "open-matchday:140:test"
    assert result["all_matches"][0]["odds_available"] is False



def test_scanner_ranking_does_not_use_odds_profile_as_tiebreaker():
    from tools.scanner import _rank_key

    higher_ev_high_variance = {
        "primary_pick": {
            "status": "LEAN",
            "odds_profile": "HIGH_VARIANCE",
            "expected_value": 0.12,
            "model_probability": 0.56,
        }
    }
    lower_ev_preferred_band = {
        "primary_pick": {
            "status": "LEAN",
            "odds_profile": "PREFERRED",
            "expected_value": 0.05,
            "model_probability": 0.60,
        }
    }

    ranked = sorted(
        [lower_ev_preferred_band, higher_ev_high_variance],
        key=_rank_key,
    )
    assert ranked[0] is higher_ev_high_variance
