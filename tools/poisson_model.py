"""Transparent Poisson baseline for football score and market probabilities.

This is an experimental baseline, not a validated betting model. It uses
recent team goal rates only; small samples and absent opponent/league
adjustments must remain explicit in the output.
"""
from __future__ import annotations

import math
from typing import Any


def _poisson_pmf(rate: float, goals: int) -> float:
    return math.exp(-rate) * rate ** goals / math.factorial(goals)


def _team_rate(form: dict[str, Any], key: str) -> float | None:
    if not form or not form.get("available"):
        return None
    value = form.get(key)
    try:
        rate = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(rate) or rate < 0:
        return None
    return rate


def estimate_goal_rates(
    home_form: dict[str, Any],
    away_form: dict[str, Any],
) -> dict[str, Any]:
    """Estimate home/away scoring rates from the two teams' recent averages."""
    hs = _team_rate(home_form, "average_goals_scored")
    hc = _team_rate(home_form, "average_goals_conceded")
    ass = _team_rate(away_form, "average_goals_scored")
    ac = _team_rate(away_form, "average_goals_conceded")

    if None in (hs, hc, ass, ac):
        return {
            "available": False,
            "reason": "Both teams need recent scored and conceded goal averages.",
            "lambda_home": None,
            "lambda_away": None,
        }

    # Symmetric attack-vs-defence blend; home advantage is not yet calibrated.
    lambda_home = max(0.05, min(4.5, (hs + ac) / 2.0))
    lambda_away = max(0.05, min(4.5, (ass + hc) / 2.0))
    sample_home = int(home_form.get("matches_played") or 0)
    sample_away = int(away_form.get("matches_played") or 0)

    return {
        "available": True,
        "method": "recent_attack_defence_average",
        "lambda_home": round(lambda_home, 4),
        "lambda_away": round(lambda_away, 4),
        "sample_home": sample_home,
        "sample_away": sample_away,
        "limitations": [
            "Experimental baseline; not calibrated or backtested.",
            "Recent form sample is small and may not represent team strength.",
            "No league scoring baseline, opponent-strength adjustment or calibrated home advantage.",
        ],
    }


def build_score_matrix(lambda_home: float, lambda_away: float, max_goals: int = 10) -> dict[str, Any]:
    """Build independent-Poisson score probabilities up to max_goals."""
    if not (0 < lambda_home <= 4.5 and 0 < lambda_away <= 4.5):
        raise ValueError("Goal rates must be in the interval (0, 4.5].")
    home_p = [_poisson_pmf(lambda_home, g) for g in range(max_goals + 1)]
    away_p = [_poisson_pmf(lambda_away, g) for g in range(max_goals + 1)]
    matrix = [[h * a for a in away_p] for h in home_p]
    mass = sum(map(sum, matrix))
    if mass <= 0:
        raise ValueError("Score matrix has no probability mass.")
    # Normalize the truncated matrix so derived markets sum to one.
    matrix = [[value / mass for value in row] for row in matrix]
    return {
        "max_goals": max_goals,
        "probability_mass_before_normalization": mass,
        "matrix": matrix,
    }


def derive_market_probabilities(matrix: dict[str, Any]) -> dict[str, float]:
    scores = matrix["matrix"]
    home_win = draw = away_win = over_25 = btts = 0.0
    for h, row in enumerate(scores):
        for a, probability in enumerate(row):
            if h > a:
                home_win += probability
            elif h == a:
                draw += probability
            else:
                away_win += probability
            if h + a >= 3:
                over_25 += probability
            if h > 0 and a > 0:
                btts += probability
    return {
        "home_win": home_win,
        "draw": draw,
        "away_win": away_win,
        "over_2_5": over_25,
        "under_2_5": 1.0 - over_25,
        "btts_yes": btts,
        "btts_no": 1.0 - btts,
    }


def forecast_from_recent_form(
    home_form: dict[str, Any],
    away_form: dict[str, Any],
) -> dict[str, Any]:
    rates = estimate_goal_rates(home_form, away_form)
    if not rates["available"]:
        return {"available": False, "status": "INSUFFICIENT_DATA", **rates}
    score_matrix = build_score_matrix(rates["lambda_home"], rates["lambda_away"])
    markets = derive_market_probabilities(score_matrix)
    candidates = []
    labels = {
        "home_win": ("1X2", "Home win"),
        "draw": ("1X2", "Draw"),
        "away_win": ("1X2", "Away win"),
        "over_2_5": ("Total goals 2.5", "Over 2.5"),
        "under_2_5": ("Total goals 2.5", "Under 2.5"),
        "btts_yes": ("Both teams to score", "Yes"),
        "btts_no": ("Both teams to score", "No"),
    }
    for key, probability in markets.items():
        market, selection = labels[key]
        candidates.append({
            "market": market,
            "selection": selection,
            "model_probability": round(probability, 6),
            "fair_odds": round(1.0 / probability, 3) if probability > 0 else None,
            "odds": None,
            "status": "WATCHLIST",
            "reason": "Experimental Poisson baseline; bookmaker price and out-of-sample validation are not yet connected.",
        })
    candidates.sort(key=lambda item: item["model_probability"], reverse=True)
    return {
        "available": True,
        "model": "experimental_poisson_baseline",
        "validated": False,
        "goal_rates": rates,
        "score_matrix": score_matrix,
        "market_probabilities": {k: round(v, 6) for k, v in markets.items()},
        "primary_forecast": candidates[0],
        "candidates": candidates,
        "warning": "Forecast probabilities are experimental and must not be treated as validated betting advice.",
    }
