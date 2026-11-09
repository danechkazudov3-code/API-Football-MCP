"""Experimental Poisson baseline with league and venue adjustments.

This is a transparent baseline, not a validated betting model. When season
statistics are available, scoring rates are normalized against the league
baseline and split by home/away venue. Recent form remains a documented fallback.
"""
from __future__ import annotations
import math
from typing import Any


def _poisson_pmf(rate: float, goals: int) -> float:
    return math.exp(-rate) * rate ** goals / math.factorial(goals)


def _rate(form: dict[str, Any] | None, key: str) -> float | None:
    if not form or not form.get("available"):
        return None
    try:
        value = float(form.get(key))
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value >= 0 else None


def extract_team_rates(stats_response: dict[str, Any]) -> dict[str, Any]:
    """Extract API-Football team home/away scoring and conceding averages."""
    if not stats_response or not stats_response.get("success"):
        return {"available": False}
    rows = stats_response.get("data") or []
    if not rows:
        return {"available": False}
    goals = rows[0].get("goals") or {}
    scored = (goals.get("for") or {}).get("average") or {}
    conceded = (goals.get("against") or {}).get("average") or {}
    try:
        values = {
            "scored_home": float(scored.get("home")),
            "scored_away": float(scored.get("away")),
            "conceded_home": float(conceded.get("home")),
            "conceded_away": float(conceded.get("away")),
        }
    except (TypeError, ValueError):
        return {"available": False}
    if not all(math.isfinite(v) and v >= 0 for v in values.values()):
        return {"available": False}
    return {"available": True, **values}


def extract_league_goal_baseline(standings_response: dict[str, Any]) -> dict[str, Any]:
    """Estimate goals per team-match from the current league table."""
    if not standings_response or not standings_response.get("success"):
        return {"available": False}
    total_goals = 0
    total_team_matches = 0
    for response_item in standings_response.get("data") or []:
        league = response_item.get("league") or {}
        groups = league.get("standings") or []
        for group in groups:
            for row in group:
                all_stats = row.get("all") or {}
                try:
                    played = int(all_stats.get("played") or 0)
                    goals_for = int((all_stats.get("goals") or {}).get("for") or 0)
                except (TypeError, ValueError):
                    continue
                if played > 0:
                    total_goals += goals_for
                    total_team_matches += played
    if total_team_matches == 0:
        return {"available": False}
    return {
        "available": True,
        "goals_per_team_match": total_goals / total_team_matches,
        "teams_sampled": len([
            row for item in standings_response.get("data") or []
            for group in (item.get("league") or {}).get("standings") or []
            for row in group if int((row.get("all") or {}).get("played") or 0) > 0
        ]),
    }


def estimate_goal_rates(
    home_form: dict[str, Any],
    away_form: dict[str, Any],
    *,
    home_team_rates: dict[str, Any] | None = None,
    away_team_rates: dict[str, Any] | None = None,
    league_baseline: float | None = None,
    home_advantage: float = 1.08,
) -> dict[str, Any]:
    """Estimate goal intensities with venue, league and opponent-defence effects."""
    if not 0.90 <= home_advantage <= 1.20:
        raise ValueError("home_advantage must be between 0.90 and 1.20.")
    baseline = league_baseline if league_baseline and 0.5 <= league_baseline <= 2.5 else None
    h = home_team_rates or {}
    a = away_team_rates or {}

    if h.get("available") and a.get("available") and baseline:
        # Attack and defence are ratios to the league scoring baseline.
        home_attack = h["scored_home"] / baseline
        away_defence = a["conceded_away"] / baseline
        away_attack = a["scored_away"] / baseline
        home_defence = h["conceded_home"] / baseline
        lambda_home = baseline * home_attack * away_defence * home_advantage
        lambda_away = baseline * away_attack * home_defence / home_advantage
        method = "league_normalized_venue_attack_defence"
        limitations = [
            "Opponent strength is approximated through season-long attack/defence rates, not an individual opponent rating.",
            "Home-advantage multiplier is a configurable baseline, not yet league-calibrated.",
            "Team and league season aggregates may include matches earlier in the current season only; they are not a historical walk-forward dataset.",
        ]
    else:
        hs = _rate(home_form, "average_goals_scored")
        hc = _rate(home_form, "average_goals_conceded")
        ass = _rate(away_form, "average_goals_scored")
        ac = _rate(away_form, "average_goals_conceded")
        if None in (hs, hc, ass, ac):
            return {
                "available": False,
                "reason": "Need both teams' recent form, or both season team statistics plus league baseline.",
                "lambda_home": None, "lambda_away": None,
            }
        # Recent-form fallback is shrunk toward a neutral scoring baseline.
        base = baseline or 1.35
        shrink = 0.65
        home_attack = shrink * hs + (1 - shrink) * base
        away_defence = shrink * ac + (1 - shrink) * base
        away_attack = shrink * ass + (1 - shrink) * base
        home_defence = shrink * hc + (1 - shrink) * base
        lambda_home = (home_attack + away_defence) / 2 * home_advantage
        lambda_away = (away_attack + home_defence) / 2 / home_advantage
        method = "shrunk_recent_form_with_home_advantage"
        limitations = [
            "Fallback uses a small recent-form sample and no direct opponent ratings.",
            "League baseline is a generic prior unless season standings were supplied.",
            "Home-advantage multiplier is not yet empirically calibrated.",
        ]

    lambda_home = max(0.05, min(4.5, lambda_home))
    lambda_away = max(0.05, min(4.5, lambda_away))
    return {
        "available": True,
        "method": method,
        "lambda_home": round(lambda_home, 4),
        "lambda_away": round(lambda_away, 4),
        "league_baseline": round(baseline, 4) if baseline else None,
        "home_advantage": home_advantage,
        "limitations": limitations + ["Experimental model; not calibrated or backtested."],
    }


def build_score_matrix(lambda_home: float, lambda_away: float, max_goals: int = 10) -> dict[str, Any]:
    if not (0 < lambda_home <= 4.5 and 0 < lambda_away <= 4.5):
        raise ValueError("Goal rates must be in the interval (0, 4.5].")
    home_p = [_poisson_pmf(lambda_home, g) for g in range(max_goals + 1)]
    away_p = [_poisson_pmf(lambda_away, g) for g in range(max_goals + 1)]
    matrix = [[h * a for a in away_p] for h in home_p]
    mass = sum(map(sum, matrix))
    if mass <= 0:
        raise ValueError("Score matrix has no probability mass.")
    matrix = [[value / mass for value in row] for row in matrix]
    return {"max_goals": max_goals, "probability_mass_before_normalization": mass, "matrix": matrix}


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
        "home_win": home_win, "draw": draw, "away_win": away_win,
        "over_2_5": over_25, "under_2_5": 1.0 - over_25,
        "btts_yes": btts, "btts_no": 1.0 - btts,
    }


def forecast_from_recent_form(
    home_form: dict[str, Any],
    away_form: dict[str, Any],
    *,
    home_team_rates: dict[str, Any] | None = None,
    away_team_rates: dict[str, Any] | None = None,
    league_baseline: float | None = None,
    home_advantage: float = 1.08,
) -> dict[str, Any]:
    rates = estimate_goal_rates(
        home_form, away_form, home_team_rates=home_team_rates,
        away_team_rates=away_team_rates, league_baseline=league_baseline,
        home_advantage=home_advantage,
    )
    if not rates["available"]:
        return {"available": False, "status": "INSUFFICIENT_DATA", **rates}
    score_matrix = build_score_matrix(rates["lambda_home"], rates["lambda_away"])
    markets = derive_market_probabilities(score_matrix)
    labels = {
        "home_win": ("1X2", "Home win"), "draw": ("1X2", "Draw"),
        "away_win": ("1X2", "Away win"),
        "over_2_5": ("Total goals 2.5", "Over 2.5"),
        "under_2_5": ("Total goals 2.5", "Under 2.5"),
        "btts_yes": ("Both teams to score", "Yes"),
        "btts_no": ("Both teams to score", "No"),
    }
    candidates = []
    for key, probability in markets.items():
        market, selection = labels[key]
        candidates.append({
            "market": market, "selection": selection,
            "model_probability": round(probability, 6),
            "fair_odds": round(1.0 / probability, 3) if probability > 0 else None,
            "odds": None, "status": "WATCHLIST",
            "reason": "Experimental Poisson baseline; bookmaker price and out-of-sample validation are not yet connected.",
        })
    candidates.sort(key=lambda item: item["model_probability"], reverse=True)
    return {
        "available": True, "model": "experimental_poisson_baseline_v2",
        "validated": False, "goal_rates": rates, "score_matrix": score_matrix,
        "market_probabilities": {k: round(v, 6) for k, v in markets.items()},
        "primary_forecast": candidates[0], "candidates": candidates,
        "warning": "Experimental probabilities; not calibrated or backtested.",
    }
