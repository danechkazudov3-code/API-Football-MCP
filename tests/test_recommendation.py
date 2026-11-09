"""Tests for automatic best-price extraction and bet recommendation."""

import pytest

from tools.recommendation import extract_best_prices, predict_match_bet


def test_extract_best_price_across_all_bookmakers():
    response = {
        "success": True,
        "data": [{
            "bookmakers": [
                {"name": "Book A", "bets": [
                    {"name": "Match Winner", "values": [
                        {"value": "Home", "odd": "2.00"},
                        {"value": "Draw", "odd": "3.10"},
                    ]},
                    {"name": "Goals Over/Under", "values": [
                        {"value": "Over 2.5", "odd": "1.80"},
                    ]},
                    {"name": "Both Teams Score", "values": [
                        {"value": "Yes", "odd": "1.75"},
                    ]},
                ]},
                {"name": "Book B", "bets": [
                    {"name": "Match Winner", "values": [
                        {"value": "Home", "odd": "2.12"},
                    ]},
                    {"name": "Goals Over/Under", "values": [
                        {"value": "Over 2.5", "odd": "1.90"},
                    ]},
                ]},
            ],
        }],
    }
    prices = extract_best_prices(response)
    assert prices["home_win"] == {"odds": 2.12, "bookmaker": "Book B"}
    assert prices["over_2_5"] == {"odds": 1.90, "bookmaker": "Book B"}
    assert prices["draw"]["odds"] == 3.10
    assert prices["btts_yes"]["bookmaker"] == "Book A"


def test_invalid_or_failed_odds_response_returns_empty_prices():
    assert extract_best_prices({"success": False, "error": "unavailable"}) == {}
    assert extract_best_prices({"success": True, "data": []}) == {}


@pytest.mark.asyncio
async def test_predict_match_bet_keeps_candidates_when_odds_unavailable(monkeypatch):
    import tools.recommendation as recommendation

    async def fake_analysis(_fixture_id):
        return {
            "success": True,
            "fixture": {"id": 123},
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


@pytest.mark.asyncio
async def test_predict_match_bet_marks_positive_unvalidated_ev_as_lean(monkeypatch):
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
            "data": [{
                "bookmakers": [{
                    "name": "Book B",
                    "bets": [{
                        "name": "Match Winner",
                        "values": [{"value": "Home", "odd": "2.00"}],
                    }],
                }],
            }],
        }

    monkeypatch.setattr(recommendation, "analyze_match", fake_analysis)
    monkeypatch.setattr(recommendation, "api_request", fake_odds)

    result = await predict_match_bet(123)
    assert result["primary_pick"]["odds"] == 2.0
    assert result["primary_pick"]["bookmaker"] == "Book B"
    assert result["primary_pick"]["expected_value"] == 0.2
    assert result["primary_pick"]["status"] == "LEAN"
    assert result["primary_pick"]["status"] != "VALUE_BET"
