import pytest
from tools.live_model import estimate_remaining_goal_rates, derive_live_probabilities


def test_remaining_goal_rates_decline_as_match_time_runs_out():
    early = estimate_remaining_goal_rates(1.5, 1.2, 20)
    late = estimate_remaining_goal_rates(1.5, 1.2, 80)
    assert early["lambda_home_remaining"] > late["lambda_home_remaining"]
    assert early["validated"] is False


def test_red_card_reduces_sent_off_team_attack_and_boosts_opponent():
    baseline = estimate_remaining_goal_rates(1.4, 1.1, 60)
    home_red = estimate_remaining_goal_rates(1.4, 1.1, 60, red_cards_home=1)
    assert home_red["lambda_home_remaining"] < baseline["lambda_home_remaining"]
    assert home_red["lambda_away_remaining"] > baseline["lambda_away_remaining"]


def test_live_stats_adjust_pressure_but_are_bounded():
    result = estimate_remaining_goal_rates(
        1.3, 1.2, 55, shots_home=18, shots_away=3,
        shots_on_target_home=8, shots_on_target_away=1,
    )
    assert 0.85 <= result["pressure_multiplier_home"] <= 1.15
    assert result["lambda_home_remaining"] > result["lambda_away_remaining"]


def test_final_probabilities_respect_current_score():
    probs = derive_live_probabilities(0.05, 0.05, 2, 0)
    assert probs["home_win"] > 0.95
    assert probs["home_win"] + probs["draw"] + probs["away_win"] == pytest.approx(1.0)
    assert probs["over_2_5"] > 0.99
