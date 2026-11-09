import pytest

from tools.poisson_model import (
    build_score_matrix,
    derive_market_probabilities,
    estimate_goal_rates,
    forecast_from_recent_form,
)


def _form(scored, conceded, count=5):
    return {
        "available": True,
        "average_goals_scored": scored,
        "average_goals_conceded": conceded,
        "matches_played": count,
    }


def test_estimate_goal_rates_blends_attack_and_opponent_defence():
    result = estimate_goal_rates(_form(2.0, 1.0), _form(1.0, 2.0))
    assert result["available"] is True
    assert result["lambda_home"] == 2.0
    assert result["lambda_away"] == 1.0


def test_missing_form_returns_unavailable():
    result = estimate_goal_rates(_form(1.5, 1.0), {"available": False})
    assert result["available"] is False


def test_score_matrix_and_market_probabilities_are_normalized():
    matrix = build_score_matrix(1.4, 1.1)
    assert sum(map(sum, matrix["matrix"])) == pytest.approx(1.0)
    markets = derive_market_probabilities(matrix)
    assert markets["home_win"] + markets["draw"] + markets["away_win"] == pytest.approx(1.0)
    assert markets["over_2_5"] + markets["under_2_5"] == pytest.approx(1.0)
    assert markets["btts_yes"] + markets["btts_no"] == pytest.approx(1.0)


def test_invalid_rates_are_rejected():
    with pytest.raises(ValueError):
        build_score_matrix(0, 1.0)


def test_forecast_shows_candidates_but_does_not_claim_value():
    result = forecast_from_recent_form(_form(1.8, 1.0), _form(1.2, 1.5))
    assert result["available"] is True
    assert result["validated"] is False
    assert len(result["candidates"]) == 7
    assert result["primary_forecast"]["status"] == "WATCHLIST"
    assert result["primary_forecast"]["odds"] is None
