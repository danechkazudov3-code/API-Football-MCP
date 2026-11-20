"""Experimental in-play model for goals remaining in a football match."""
from __future__ import annotations
from typing import Any
from tools.poisson_model import build_score_matrix


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def estimate_remaining_goal_rates(
    prematch_lambda_home: float,
    prematch_lambda_away: float,
    elapsed: int,
    *,
    shots_home: float = 0,
    shots_away: float = 0,
    shots_on_target_home: float = 0,
    shots_on_target_away: float = 0,
    red_cards_home: int = 0,
    red_cards_away: int = 0,
    regulation_end_minute: int = 95,
) -> dict[str, Any]:
    """Estimate scoring intensities for remaining time, not the full match."""
    if not 0 <= elapsed <= 130:
        raise ValueError("elapsed must be between 0 and 130 minutes.")
    if prematch_lambda_home <= 0 or prematch_lambda_away <= 0:
        raise ValueError("Pre-match goal rates must be positive.")
    if min(red_cards_home, red_cards_away) < 0:
        raise ValueError("Red-card counts cannot be negative.")

    remaining_fraction = _clamp((regulation_end_minute - elapsed) / 90.0, 0.0, 1.0)
    total_sot = max(4.0, shots_on_target_home + shots_on_target_away)
    total_shots = max(12.0, shots_home + shots_away)
    home_pressure = 1.0 + 0.10 * (shots_on_target_home - shots_on_target_away) / total_sot
    home_pressure += 0.04 * (shots_home - shots_away) / total_shots
    away_pressure = 2.0 - home_pressure
    home_pressure = _clamp(home_pressure, 0.85, 1.15)
    away_pressure = _clamp(away_pressure, 0.85, 1.15)

    home_card_factor = (0.82 ** red_cards_home) * (1.18 ** red_cards_away)
    away_card_factor = (0.82 ** red_cards_away) * (1.18 ** red_cards_home)
    lambda_home = max(0.001, prematch_lambda_home * remaining_fraction * home_pressure * home_card_factor)
    lambda_away = max(0.001, prematch_lambda_away * remaining_fraction * away_pressure * away_card_factor)
    return {
        "lambda_home_remaining": round(lambda_home, 4),
        "lambda_away_remaining": round(lambda_away, 4),
        "elapsed": elapsed,
        "remaining_fraction": round(remaining_fraction, 4),
        "pressure_multiplier_home": round(home_pressure, 4),
        "pressure_multiplier_away": round(away_pressure, 4),
        "red_cards_home": red_cards_home,
        "red_cards_away": red_cards_away,
        "method": "remaining_time_poisson_with_live_pressure_and_red_cards",
        "validated": False,
    }


def derive_live_probabilities(
    lambda_home_remaining: float,
    lambda_away_remaining: float,
    score_home: int,
    score_away: int,
) -> dict[str, float]:
    """Convert remaining-goal distribution into final-outcome probabilities."""
    if score_home < 0 or score_away < 0:
        raise ValueError("Current score cannot be negative.")
    matrix = build_score_matrix(lambda_home_remaining, lambda_away_remaining, max_goals=8)["matrix"]
    result = {"home_win": 0.0, "draw": 0.0, "away_win": 0.0,
              "over_2_5": 0.0, "under_2_5": 0.0, "btts_yes": 0.0, "btts_no": 0.0}
    for add_home, row in enumerate(matrix):
        for add_away, probability in enumerate(row):
            final_home = score_home + add_home
            final_away = score_away + add_away
            if final_home > final_away:
                result["home_win"] += probability
            elif final_home == final_away:
                result["draw"] += probability
            else:
                result["away_win"] += probability
            if final_home + final_away >= 3:
                result["over_2_5"] += probability
            if final_home > 0 and final_away > 0:
                result["btts_yes"] += probability
    result["under_2_5"] = 1.0 - result["over_2_5"]
    result["btts_no"] = 1.0 - result["btts_yes"]
    return result
