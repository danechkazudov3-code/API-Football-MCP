"""Chronological walk-forward evaluation for historical football fixtures.

Every forecast is made before the fixture is added to team/league history.
This evaluates probability quality only; profitability requires historical odds.
"""
from __future__ import annotations
import math
from typing import Any
from tools.poisson_model import forecast_from_recent_form
from tools.football_data_provider import fetch_football_data_fixtures


FINISHED = {"FT", "AET", "PEN"}


def _fixture_parts(item: dict[str, Any]) -> tuple[str, int, int, int, int] | None:
    fixture = item.get("fixture") or {}
    if (fixture.get("status") or {}).get("short") not in FINISHED:
        return None
    teams = item.get("teams") or {}
    home = (teams.get("home") or {}).get("id")
    away = (teams.get("away") or {}).get("id")
    goals = item.get("goals") or {}
    hg, ag = goals.get("home"), goals.get("away")
    if home is None or away is None or hg is None or ag is None:
        return None
    return str(fixture.get("date") or ""), int(home), int(away), int(hg), int(ag)


def _form(history: list[tuple[int, int]], team_name: str, limit: int) -> dict[str, Any]:
    recent = history[-limit:]
    if not recent:
        return {"available": False, "team": team_name}
    return {
        "available": True, "team": team_name, "matches_played": len(recent),
        "average_goals_scored": sum(x[0] for x in recent) / len(recent),
        "average_goals_conceded": sum(x[1] for x in recent) / len(recent),
    }


def _safe_log(value: float) -> float:
    return math.log(max(1e-12, min(1.0, value)))


def run_walk_forward_backtest(
    fixtures: list[dict[str, Any]],
    *,
    min_history: int = 5,
    history_window: int = 10,
    home_advantage: float = 1.08,
) -> dict[str, Any]:
    """Evaluate a chronological fixture list without using future results."""
    if min_history < 1 or history_window < min_history:
        raise ValueError("Require 1 <= min_history <= history_window.")
    ordered = sorted(
        (item for item in fixtures if _fixture_parts(item)),
        key=lambda item: _fixture_parts(item)[0],
    )
    team_history: dict[tuple[str, int], list[tuple[int, int]]] = {}
    league_history: dict[str, list[tuple[int, int]]] = {}
    predictions: list[dict[str, Any]] = []

    # Group by calendar day. Football-Data CSVs contain dates but no kickoff
    # times, so results from one matchday must not influence another forecast
    # from the same day.
    from itertools import groupby

    for match_day, day_iter in groupby(
        ordered,
        key=lambda item: (_fixture_parts(item) or ("", 0, 0, 0, 0))[0][:10],
    ):
        day_items = list(day_iter)
        day_results: list[tuple[str, int, int, int, int, dict[str, Any]]] = []

        # Generate every forecast for this date using history strictly before it.
        for item in day_items:
            parts = _fixture_parts(item)
            if parts is None:
                continue
            date_value, home_id, away_id, hg, ag = parts
            league_id = str((item.get("league") or {}).get("id", "unknown"))
            home_key, away_key = (league_id, home_id), (league_id, away_id)
            home_hist = team_history.get(home_key, [])
            away_hist = team_history.get(away_key, [])
            league_hist = league_history.get(league_id, [])

            if len(home_hist) >= min_history and len(away_hist) >= min_history and league_hist:
                total_goals = sum(h + a for h, a in league_hist)
                league_baseline = total_goals / (2 * len(league_hist))
                forecast = forecast_from_recent_form(
                    _form(home_hist, "home", history_window),
                    _form(away_hist, "away", history_window),
                    league_baseline=league_baseline,
                    home_advantage=home_advantage,
                )
                if forecast.get("available"):
                    probabilities = forecast["market_probabilities"]
                    actual_result = "home_win" if hg > ag else "away_win" if hg < ag else "draw"
                    predictions.append({
                        "fixture_id": (item.get("fixture") or {}).get("id"),
                        "date": date_value, "league_id": league_id,
                        "probabilities": probabilities,
                        "actual_result": actual_result,
                        "actual_over_2_5": hg + ag >= 3,
                        "actual_score": [hg, ag],
                        "home_team": ((item.get("teams") or {}).get("home") or {}).get("name"),
                        "away_team": ((item.get("teams") or {}).get("away") or {}).get("name"),
                        "historical_odds": item.get("historical_odds"),
                    })
            day_results.append((league_id, home_id, away_id, hg, ag, item))

        # Only after all forecasts for this date are complete, add that day's results.
        for league_id, home_id, away_id, hg, ag, _item in day_results:
            team_history.setdefault((league_id, home_id), []).append((hg, ag))
            team_history.setdefault((league_id, away_id), []).append((ag, hg))
            league_history.setdefault(league_id, []).append((hg, ag))

    if not predictions:
        return {
            "success": True, "status": "INSUFFICIENT_SAMPLE",
            "fixtures_received": len(fixtures), "fixtures_evaluated": 0,
            "minimum_history": min_history,
            "reason": "Not enough earlier matches per team to make leakage-free forecasts.",
            "profitability_evaluated": False,
        }

    brier_1x2 = []
    log_loss_1x2 = []
    correct = 0
    brier_over = []
    for prediction in predictions:
        probs = prediction["probabilities"]
        actual = prediction["actual_result"]
        brier_1x2.append(sum((probs[key] - (1.0 if key == actual else 0.0)) ** 2
                             for key in ("home_win", "draw", "away_win")))
        log_loss_1x2.append(-_safe_log(probs[actual]))
        chosen = max(("home_win", "draw", "away_win"), key=lambda key: probs[key])
        correct += chosen == actual
        p_over = probs["over_2_5"]
        y_over = 1.0 if prediction["actual_over_2_5"] else 0.0
        brier_over.append((p_over - y_over) ** 2)

    n = len(predictions)
    return {
        "success": True, "status": "EVALUATED_PROBABILITY_QUALITY_ONLY",
        "fixtures_received": len(fixtures), "fixtures_evaluated": n,
        "minimum_history": min_history, "history_window": history_window,
        "chronological_walk_forward": True,
        "metrics": {
            "1x2_brier_score": sum(brier_1x2) / n,
            "1x2_log_loss": sum(log_loss_1x2) / n,
            "1x2_accuracy": correct / n,
            "over_2_5_brier_score": sum(brier_over) / n,
        },
        "predictions": predictions,
        "profitability_evaluated": False,
        "odds_coverage": sum(bool(p.get("historical_odds") and all(p["historical_odds"].get(k) for k in ("home", "draw", "away"))) for p in predictions),
        "profitability_reason": "Historical closing odds may be present, but no timestamped opening/closing series is available; ROI and CLV are not calculated by this baseline.",
        "warning": "This is an initial experimental baseline. It does not establish profitability or VALUE_BET eligibility.",
    }


from api_client import api_request, _error_response
from server import mcp


@mcp.tool()
async def backtest_league(
    league_id: int,
    season: int,
    from_date: str,
    to_date: str,
    min_history: int = 5,
    source: str = "football_data",
) -> dict[str, Any]:
    """Run a chronological probability backtest on finished fixtures in a date range.

    Historical bookmaker odds are not included by API-Football's ordinary fixtures
    endpoint, so this tool reports probability metrics, not ROI.
    """
    if not league_id or not season or not from_date or not to_date:
        return _error_response("league_id, season, from_date and to_date are required.")
    try:
        from datetime import date
        start, end = date.fromisoformat(from_date), date.fromisoformat(to_date)
        span = (end - start).days
        if span < 0 or span > 180:
            return _error_response("Date range must be chronological and no longer than 180 days.")
    except ValueError:
        return _error_response("Dates must use YYYY-MM-DD format.")
    if source == "football_data":
        result = await fetch_football_data_fixtures(
            league_id=league_id, season=season, from_date=from_date, to_date=to_date
        )
    elif source == "api_football":
        result = await api_request("/fixtures", {
            "league": league_id, "season": season,
            "from": from_date, "to": to_date, "status": "FT-AET-PEN",
        })
    else:
        return _error_response("source must be football_data or api_football.")
    if not result.get("success"):
        return result
    report = run_walk_forward_backtest(result.get("data") or [], min_history=min_history)
    report["data_source"] = result.get("source", "api-football")
    report["source_url"] = result.get("url")
    report["league_id"] = league_id
    report["season"] = season
    report["date_range"] = {"from": from_date, "to": to_date}
    report["rate_limit_remaining"] = result.get("rate_limit_remaining")
    report["historical_odds_available"] = result.get("odds_available", 0)
    return report
