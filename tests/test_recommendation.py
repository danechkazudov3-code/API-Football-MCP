"""Tests for bookmaker-consistent odds extraction and bet recommendation."""

import pytest

from tools.recommendation import extract_best_prices, predict_match_bet


def test_extract_best_prices_and_no_vig_are_bookmaker_consistent():
    response = {
        "success": True,
        "retrieved_at": "2026-11-10T12:00:00+00:00",
        "data": [{
            "update": "2026-11-10T11:59:00+00:00",
            "bookmakers": [
                {"name": "Book A", "bets": [
                    {"name": "Match Winner", "values": [
                        {"value": "Home", "odd": "2.00"},
                        {"value": "Draw", "odd": "3.10"},
                        {"value": "Away", "odd": "3.80"},
                    ]},
                    {"name": "Goals Over/Under", "values": [
                        {"value": "Over 2.5", "odd": "1.80"},
                        {"value": "Under 2.5", "odd": "2.00"},
                    ]},
                    {"name": "Both Teams Score", "values": [
                        {"value": "Yes", "odd": "1.75"},
                        {"value": "No", "odd": "2.10"},
                    ]},
                ]},
                {"name": "Book B", "bets": [
                    {"name": "Match Winner", "values": [
                        {"value": "Home", "odd": "2.12"},
                        {"value": "Draw", "odd": "3.20"},
                        {"value": "Away", "odd": "3.60"},
                    ]},
                    {"name": "Goals Over/Under", "values": [
                        {"value": "Over 2.5", "odd": "1.90"},
                        {"value": "Under 2.5", "odd": "1.95"},
                    ]},
                ]},
            ],
        }],
    }

    prices = extract_best_prices(response)
    home_sum = (1 / 2.12) + (1 / 3.20) + (1 / 3.60)
    assert prices["home_win"]["odds"] == 2.12
    assert prices["home_win"]["bookmaker"] == "Book B"
    assert prices["home_win"]["no_vig_probability"] == pytest.approx((1 / 2.12) / home_sum, abs=1e-6)
    assert prices["home_win"]["overround"] == pytest.approx(home_sum - 1, abs=1e-6)
    assert prices["home_win"]["provider_updated_at"] == "2026-11-10T11:59:00+00:00"
    assert prices["home_win"]["odds_observed_at"] == "2026-11-10T12:00:00+00:00"
    assert prices["over_2_5"]["odds"] == 1.90
    assert prices["over_2_5"]["no_vig_probability"] is not None
    assert prices["btts_yes"]["bookmaker"] == "Book A"
    assert prices["btts_yes"]["no_vig_probability"] is not None


def test_no_vig_is_not_synthesized_from_different_bookmakers():
    response = {
        "success": True,
        "data": [{
            "bookmakers": [
                {"name": "Book A", "bets": [{"name": "Match Winner", "values": [
                    {"value": "Home", "odd": "2.00"}, {"value": "Draw", "odd": "3.10"},
                ]}]},
                {"name": "Book B", "bets": [{"name": "Match Winner", "values": [
                    {"value": "Away", "odd": "3.80"},
                ]}]},
            ],
        }],
    }
    prices = extract_best_prices(response)
    assert prices["home_win"]["no_vig_probability"] is None
    assert prices["draw"]["no_vig_probability"] is None
    assert prices["away_win"]["no_vig_probability"] is None
    assert prices["home_win"]["market_complete"] is False


def test_incomplete_or_failed_odds_response_returns_empty_or_unpriced_data():
    assert extract_best_prices({"success": False, "error": "unavailable"}) == {}
    assert extract_best_prices({"success": True, "data": []}) == {}


@pytest.mark.asyncio
async def test_predict_match_bet_keeps_candidates_when_odds_unavailable(monkeypatch):
    import tools.recommendation as recommendation

    async def fake_analysis(_fixture_id):
        return {
            "success": True,
            "fixture": {"id": 123},
            "analysis_status": "DATA_COLLECTION_WITH_FORM",
            "recent_form": {"home": {"form": "WWDLW"}, "away": {"form": "LDWLW"}},
            "head_to_head": {"available": True, "matches_played": 3},
            "injuries": {"available": True, "count": 1},
            "season_statistics": {"home": {"available": False}},
            "data_limitations": ["Test limitation"],
            "forecast": {
                "available": True,
                "model": "experimental_poisson_baseline",
                "candidates": [
                    {"market": "1X2", "selection": "Home win", "model_probability": 0.55},
                    {"market": "Total goals 2.5", "selection": "Over 2.5", "model_probability": 0.60},
                ],
            },
        }

    async def fake_odds(_endpoint, _params):
        return {"success": False, "error": "Odds unavailable", "data": []}

    monkeypatch.setattr(recommendation, "analyze_match", fake_analysis)
    monkeypatch.setattr(recommendation, "api_request", fake_odds)

    result = await predict_match_bet(123)
    assert result["success"] is True
    assert len(result["candidates"]) == 2
    assert result["primary_pick"]["selection"] == "Over 2.5"
    assert result["primary_pick"]["status"] == "INSUFFICIENT_DATA"
    assert result["odds_available"] is False
    assert result["model_validated"] is False
    assert result["match_analysis"]["recent_form"]["home"]["form"] == "WWDLW"
    assert result["match_analysis"]["head_to_head"]["matches_played"] == 3
    assert result["match_analysis"]["injuries"]["count"] == 1


@pytest.mark.asyncio
async def test_predict_match_bet_keeps_unvalidated_ev_as_lean_and_edge_is_explicit(monkeypatch):
    import tools.recommendation as recommendation

    async def fake_analysis(_fixture_id):
        return {
            "success": True,
            "fixture": {"id": 123},
            "forecast": {
                "available": True,
                "model": "experimental_poisson_baseline",
                "candidates": [
                    {"market": "1X2", "selection": "Home win", "model_probability": 0.60},
                ],
            },
        }

    async def fake_odds(_endpoint, _params):
        return {
            "success": True,
            "retrieved_at": "2026-11-10T12:00:00+00:00",
            "data": [{
                "update": "2026-11-10T11:59:00+00:00",
                "bookmakers": [{
                    "name": "PARI",
                    "bets": [{
                        "name": "Match Winner",
                        "values": [
                            {"value": "Home", "odd": "2.00"},
                            {"value": "Draw", "odd": "3.20"},
                            {"value": "Away", "odd": "3.80"},
                        ],
                    }],
                }],
            }],
        }

    monkeypatch.setattr(recommendation, "analyze_match", fake_analysis)
    monkeypatch.setattr(recommendation, "api_request", fake_odds)

    result = await predict_match_bet(123)
    pick = result["primary_pick"]
    assert pick["odds"] == 2.0
    assert pick["bookmaker"] == "PARI"
    assert pick["expected_value"] == 0.2
    assert pick["no_vig_probability"] is not None
    assert pick["edge"] > 0
    assert pick["provider_updated_at"] == "2026-11-10T11:59:00+00:00"
    assert pick["odds_observed_at"] == "2026-11-10T12:00:00+00:00"
    assert pick["status"] == "LEAN"
    assert pick["status"] != "VALUE_BET"
    assert result["most_likely_outcome"]["selection"] == "Home win"


def test_pari_allowlist_excludes_other_bookmakers():
    response = {
        "success": True,
        "data": [{
            "bookmakers": [
                {"name": "OtherBook", "bets": [{"name": "Match Winner", "values": [
                    {"value": "Home", "odd": "1.90"},
                    {"value": "Draw", "odd": "3.30"},
                    {"value": "Away", "odd": "4.10"},
                ]}]},
                {"name": "PARI", "bets": [{"name": "Match Winner", "values": [
                    {"value": "Home", "odd": "2.00"},
                    {"value": "Draw", "odd": "3.20"},
                    {"value": "Away", "odd": "3.80"},
                ]}]},
            ],
        }],
    }
    prices = extract_best_prices(response, allowed_bookmakers={"PARI"})
    assert prices["home_win"]["odds"] == 2.00
    assert prices["home_win"]["bookmaker"] == "PARI"


def test_pari_allowlist_rejects_names_that_only_start_with_pari():
    response = {
        "success": True,
        "data": [{
            "bookmakers": [{
                "name": "PARI Exchange",
                "bets": [{"name": "Match Winner", "values": [
                    {"value": "Home", "odd": "2.00"},
                    {"value": "Draw", "odd": "3.20"},
                    {"value": "Away", "odd": "3.80"},
                ]}],
            }],
        }],
    }
    assert extract_best_prices(response, allowed_bookmakers={"PARI"}) == {}
