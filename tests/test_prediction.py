"""Tests for prediction pricing and candidate selection."""

from tools.prediction import evaluate_candidate, select_primary_candidate


def test_candidate_without_probability_is_visible_but_not_priced():
    result = evaluate_candidate({"market": "Totals", "selection": "Over 2.5", "odds": 2.1})
    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["fair_odds"] is None
    assert result["expected_value"] is None


def test_positive_ev_without_validated_model_is_lean():
    result = evaluate_candidate({
        "market": "1X2", "selection": "Home", "odds": 2.2,
        "model_probability": 0.50,
    })
    assert result["expected_value"] == 0.1
    assert result["status"] == "LEAN"


def test_negative_ev_is_no_bet_but_candidate_remains_available():
    result = evaluate_candidate({
        "market": "1X2", "selection": "Away", "odds": 1.7,
        "model_probability": 0.50,
    })
    assert result["status"] == "NO_BET"
    assert result["selection"] == "Away"


def test_value_requires_validated_model_and_conservative_edge():
    candidate = {
        "market": "Totals", "selection": "Over 2.5", "odds": 2.2,
        "model_probability": 0.52, "probability_lower_bound": 0.49,
    }
    result = evaluate_candidate(candidate, model_validated=True, min_expected_value=0.05)
    assert result["status"] == "VALUE_BET"


def test_unvalidated_or_missing_uncertainty_never_becomes_value():
    candidate = {
        "market": "BTTS", "selection": "Yes", "odds": 2.0,
        "model_probability": 0.60,
    }
    result = evaluate_candidate(candidate, model_validated=True)
    assert result["status"] == "LEAN"


def test_selector_does_not_hide_no_bet_candidates():
    candidates = [
        {"status": "NO_BET", "selection": "Home"},
        {"status": "LEAN", "selection": "Over 2.5"},
        {"status": "WATCHLIST", "selection": "BTTS"},
    ]
    assert select_primary_candidate(candidates)["selection"] == "Over 2.5"


def test_selector_returns_none_for_empty_input():
    assert select_primary_candidate([]) is None


def test_edge_is_model_probability_minus_no_vig_market_probability():
    result = evaluate_candidate({
        "market": "1X2", "selection": "Home", "odds": 2.2,
        "model_probability": 0.50, "no_vig_probability": 0.46,
    })
    assert result["edge"] == 0.04


def test_edge_is_unavailable_when_bookmaker_market_is_incomplete():
    result = evaluate_candidate({
        "market": "1X2", "selection": "Home", "odds": 2.2,
        "model_probability": 0.50, "no_vig_probability": None,
    })
    assert result["edge"] is None
