import pytest
from tools.poisson_model import (
    build_score_matrix, derive_market_probabilities, estimate_goal_rates,
    forecast_from_recent_form, extract_team_rates, extract_league_goal_baseline,
    extract_standings_team_strengths, adjust_recent_form_for_opponents,
)


def _form(scored, conceded, count=5):
    return {"available": True, "average_goals_scored": scored,
            "average_goals_conceded": conceded, "matches_played": count}


def test_recent_form_fallback_is_shrunk_and_home_adjusted():
    result = estimate_goal_rates(_form(2.0, 1.0), _form(1.0, 2.0))
    assert result["available"] is True
    assert result["method"] == "opponent_adjusted_time_weighted_recent_form_fallback"
    assert result["lambda_home"] > result["lambda_away"]
    assert result["home_advantage"] == 1.08


def test_league_normalized_rates_use_venue_splits_and_opponent_defence():
    home = {"available": True, "scored_home": 2.0, "scored_away": 1.0,
            "conceded_home": 0.8, "conceded_away": 1.4}
    away = {"available": True, "scored_home": 1.4, "scored_away": 1.2,
            "conceded_home": 1.1, "conceded_away": 1.6}
    result = estimate_goal_rates(_form(1.5, 1.0), _form(1.2, 1.4),
                                 home_team_rates=home, away_team_rates=away,
                                 league_baseline=1.35, home_advantage=1.08)
    assert result["available"] is True
    assert result["method"] == "venue_season_rates_blended_with_opponent_adjusted_recent_form"
    season_home = 2.0 * 1.6 / 1.35 * 1.08
    recent_home = (1.5 + 1.4) / 2 * 1.08
    season_away = 1.2 * 0.8 / 1.35 / 1.08
    recent_away = (1.2 + 1.0) / 2 / 1.08
    assert result["lambda_home"] == pytest.approx(0.825 * season_home + 0.175 * recent_home, abs=1e-4)
    assert result["lambda_away"] == pytest.approx(0.825 * season_away + 0.175 * recent_away, abs=1e-4)
    assert result["recent_form_weight"] == pytest.approx(0.175)


def test_extract_team_rates_from_api_football_shape():
    result = extract_team_rates({"success": True, "data": [{
        "goals": {
            "for": {"average": {"home": "1.8", "away": "1.2"}},
            "against": {"average": {"home": "0.7", "away": "1.4"}},
        }
    }]})
    assert result == {"available": True, "scored_home": 1.8, "scored_away": 1.2,
                      "conceded_home": 0.7, "conceded_away": 1.4}


def test_extract_league_goal_baseline_from_standings():
    result = extract_league_goal_baseline({"success": True, "data": [{
        "league": {"standings": [[
            {"all": {"played": 10, "goals": {"for": 20}}},
            {"all": {"played": 10, "goals": {"for": 10}}},
        ]]}
    }]})
    assert result["available"] is True
    assert result["goals_per_team_match"] == pytest.approx(1.5)


def test_missing_form_and_season_data_returns_unavailable():
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



def test_extract_standings_team_strengths_creates_attack_and_defence_indices():
    result = extract_standings_team_strengths({"success": True, "data": [{
        "league": {"standings": [[
            {"team": {"id": 10}, "all": {"played": 10, "goals": {"for": 20, "against": 10}}},
            {"team": {"id": 20}, "all": {"played": 10, "goals": {"for": 10, "against": 20}}},
        ]]}
    }]})
    assert result["available"] is True
    assert result["league_baseline"] == pytest.approx(1.5)
    assert result["teams"][10]["attack_index"] == pytest.approx(20 / 10 / 1.5)
    assert result["teams"][20]["defence_index"] == pytest.approx(20 / 10 / 1.5)


def test_recent_form_is_recency_weighted_and_adjusted_for_opponent_strength():
    form = {
        "available": True, "matches_played": 2,
        "matches": [
            {"date": "2026-10-01", "opponent_id": 1, "scored": 2, "conceded": 1},
            {"date": "2026-10-08", "opponent_id": 2, "scored": 1, "conceded": 2},
        ],
    }
    strengths = {
        1: {"attack_index": 0.5, "defence_index": 2.0},
        2: {"attack_index": 2.0, "defence_index": 0.5},
    }
    result = adjust_recent_form_for_opponents(form, strengths)
    older_weight = 0.5 ** (1 / 4)
    expected_scored = (1.0 / 0.60 + (2.0 / 1.60) * older_weight) / (1 + older_weight)
    expected_conceded = (2.0 / 1.60 + (1.0 / 0.60) * older_weight) / (1 + older_weight)
    assert result["average_goals_scored"] == pytest.approx(expected_scored, abs=1e-4)
    assert result["average_goals_conceded"] == pytest.approx(expected_conceded, abs=1e-4)
    assert result["opponent_adjusted_matches"] == 2
    assert result["neutral_opponent_matches"] == 0


def test_recent_form_adjustment_accepts_string_opponent_keys():
    form = {
        "available": True, "matches_played": 1,
        "matches": [{"date": "2026-10-01", "opponent_id": "Club B",
                     "scored": 2, "conceded": 1}],
    }
    result = adjust_recent_form_for_opponents(form, {
        "Club B": {"attack_index": 1.5, "defence_index": 0.5}
    })
    assert result["opponent_adjustment_available"] is True
    assert result["opponent_adjusted_matches"] == 1
    assert result["average_goals_scored"] == pytest.approx(4.0)
    assert result["average_goals_conceded"] == pytest.approx(2 / 1.5)
