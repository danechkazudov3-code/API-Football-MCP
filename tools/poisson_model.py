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


def extract_standings_team_strengths(standings_response: dict[str, Any]) -> dict[str, Any]:
    """Build season-to-date attack/defence indices from the current league table."""
    if not standings_response or not standings_response.get("success"):
        return {"available": False, "teams": {}, "league_baseline": None}
    rows = []
    total_goals = total_team_matches = 0
    for item in standings_response.get("data") or []:
        for group in ((item.get("league") or {}).get("standings") or []):
            for row in group:
                team_id = (row.get("team") or {}).get("id")
                stats = row.get("all") or {}
                goals = stats.get("goals") or {}
                try:
                    played = int(stats.get("played") or 0)
                    scored = float(goals.get("for"))
                    conceded = float(goals.get("against"))
                except (TypeError, ValueError):
                    continue
                if team_id and played > 0 and scored >= 0 and conceded >= 0:
                    rows.append((int(team_id), played, scored, conceded))
                    total_goals += scored
                    total_team_matches += played
    if not total_team_matches:
        return {"available": False, "teams": {}, "league_baseline": None}
    baseline = total_goals / total_team_matches
    teams = {
        team_id: {
            "attack_index": (scored / played) / baseline,
            "defence_index": (conceded / played) / baseline,
            "matches_played": played,
        }
        for team_id, played, scored, conceded in rows
    }
    return {
        "available": True, "teams": teams,
        "league_baseline": baseline, "teams_sampled": len(teams),
    }


def adjust_recent_form_for_opponents(
    form: dict[str, Any] | None,
    opponent_strengths: dict[int, dict[str, Any]] | None,
    *,
    half_life_matches: float = 4.0,
) -> dict[str, Any]:
    """Time-weight recent goals and adjust them for opponents' season strength.

    Most recent match has the highest weight. Unknown opponents receive a neutral
    multiplier and are counted separately; missing data is never treated as zero.
    """
    if not form or not form.get("available") or not form.get("matches"):
        return {**(form or {}), "opponent_adjustment_available": False}
    strengths = opponent_strengths or {}
    rows = sorted(form.get("matches") or [], key=lambda row: row.get("date") or "")
    weighted = {"scored": 0.0, "conceded": 0.0}
    total_weight = 0.0
    adjusted_count = 0
    neutral_count = 0
    for age, row in enumerate(reversed(rows)):
        try:
            scored = float(row.get("scored"))
            conceded = float(row.get("conceded"))
        except (TypeError, ValueError):
            continue
        if scored < 0 or conceded < 0:
            continue
        try:
            opponent_id = int(row.get("opponent_id"))
        except (TypeError, ValueError):
            opponent_id = None
        opponent = strengths.get(opponent_id) if opponent_id is not None else None
        if opponent:
            defence_index = max(0.60, min(1.60, float(opponent.get("defence_index", 1.0))))
            attack_index = max(0.60, min(1.60, float(opponent.get("attack_index", 1.0))))
            adjusted_scored = scored / defence_index
            adjusted_conceded = conceded / attack_index
            adjusted_count += 1
        else:
            adjusted_scored, adjusted_conceded = scored, conceded
            neutral_count += 1
        weight = 0.5 ** (age / max(1.0, half_life_matches))
        weighted["scored"] += adjusted_scored * weight
        weighted["conceded"] += adjusted_conceded * weight
        total_weight += weight
    if total_weight <= 0:
        return {**form, "opponent_adjustment_available": False}
    return {
        **form,
        "average_goals_scored": round(weighted["scored"] / total_weight, 4),
        "average_goals_conceded": round(weighted["conceded"] / total_weight, 4),
        "opponent_adjustment_available": adjusted_count > 0,
        "opponent_adjusted_matches": adjusted_count,
        "neutral_opponent_matches": neutral_count,
        "recency_weighting": "exponential_half_life_4_matches",
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
    """Blend venue-specific season strength with opponent-adjusted recent form."""
    if not 0.90 <= home_advantage <= 1.20:
        raise ValueError("home_advantage must be between 0.90 and 1.20.")
    baseline = league_baseline if league_baseline and 0.5 <= league_baseline <= 2.5 else None
    h = home_team_rates or {}
    a = away_team_rates or {}

    hs = _rate(home_form, "average_goals_scored")
    hc = _rate(home_form, "average_goals_conceded")
    ass = _rate(away_form, "average_goals_scored")
    ac = _rate(away_form, "average_goals_conceded")
    home_n = int(home_form.get("matches_played") or 0)
    away_n = int(away_form.get("matches_played") or 0)
    recent_available = None not in (hs, hc, ass, ac)

    season_available = bool(h.get("available") and a.get("available") and baseline)
    if season_available:
        # Opponent attack/defence and venue are represented in season-to-date rates.
        lambda_home_season = h["scored_home"] * a["conceded_away"] / baseline * home_advantage
        lambda_away_season = a["scored_away"] * h["conceded_home"] / baseline / home_advantage
        if recent_available:
            # Recent sample is informative but noisier; cap its influence at 35%.
            recent_weight = min(0.35, max(0.10, min(home_n, away_n) / 10.0 * 0.35))
            lambda_home_recent = (hs + ac) / 2.0 * home_advantage
            lambda_away_recent = (ass + hc) / 2.0 / home_advantage
            lambda_home = (1 - recent_weight) * lambda_home_season + recent_weight * lambda_home_recent
            lambda_away = (1 - recent_weight) * lambda_away_season + recent_weight * lambda_away_recent
        else:
            recent_weight = 0.0
            lambda_home, lambda_away = lambda_home_season, lambda_away_season
        method = "venue_season_rates_blended_with_opponent_adjusted_recent_form"
        limitations = [
            "Recent form is time-decayed and opponent-adjusted using current season table strength where opponent rows are available.",
            "Current standings are a present-time snapshot; this feature must not be used as-is for historical walk-forward backtests.",
            "The blend weight and home advantage are provisional and require out-of-sample calibration.",
        ]
    elif recent_available:
        base = baseline or 1.35
        shrink = 0.65
        home_attack = shrink * hs + (1 - shrink) * base
        away_defence = shrink * ac + (1 - shrink) * base
        away_attack = shrink * ass + (1 - shrink) * base
        home_defence = shrink * hc + (1 - shrink) * base
        lambda_home = (home_attack + away_defence) / 2 * home_advantage
        lambda_away = (away_attack + home_defence) / 2 / home_advantage
        recent_weight = None
        method = "opponent_adjusted_time_weighted_recent_form_fallback"
        limitations = [
            "No complete season venue-rate baseline was available; a generic league prior was used.",
            "Opponent adjustment is only as complete as the current standings snapshot.",
            "Current standings are not time-safe for historical walk-forward backtests.",
            "Home advantage and shrinkage require out-of-sample calibration.",
        ]
    else:
        return {
            "available": False,
            "reason": "Need recent form for both teams, or both season venue rates plus league baseline.",
            "lambda_home": None, "lambda_away": None,
        }

    lambda_home = max(0.05, min(4.5, lambda_home))
    lambda_away = max(0.05, min(4.5, lambda_away))
    return {
        "available": True,
        "method": method,
        "lambda_home": round(lambda_home, 4),
        "lambda_away": round(lambda_away, 4),
        "lambda_home_season": round(lambda_home_season, 4) if season_available else None,
        "lambda_away_season": round(lambda_away_season, 4) if season_available else None,
        "recent_form_weight": round(recent_weight, 4) if recent_weight is not None else None,
        "home_recent_matches": home_n,
        "away_recent_matches": away_n,
        "league_baseline": round(baseline, 4) if baseline else None,
        "home_advantage": home_advantage,
        "limitations": limitations + ["Experimental model; not calibrated or validated for betting."],
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
            "reason": "Opponent-adjusted, time-weighted Poisson forecast; probabilities remain uncalibrated and unvalidated.",
        })
    candidates.sort(key=lambda item: item["model_probability"], reverse=True)
    return {
        "available": True, "model": "opponent_adjusted_time_weighted_poisson_v3",
        "validated": False, "goal_rates": rates, "score_matrix": score_matrix,
        "market_probabilities": {k: round(v, 6) for k, v in markets.items()},
        "primary_forecast": candidates[0], "candidates": candidates,
        "warning": "Experimental probabilities; not calibrated or validated on time-safe out-of-sample data.",
    }
