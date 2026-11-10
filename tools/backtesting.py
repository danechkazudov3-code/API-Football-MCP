"""Chronological walk-forward evaluation for historical football fixtures.

Every forecast is made before the fixture is added to team/league history.
This evaluates probability quality only; profitability requires historical odds.
"""
from __future__ import annotations
import math
from typing import Any
from tools.poisson_model import forecast_from_recent_form, adjust_recent_form_for_opponents
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


def _form(
    history: list[dict[str, Any]],
    team_name: str,
    limit: int,
) -> dict[str, Any]:
    recent = history[-limit:]
    if not recent:
        return {"available": False, "team": team_name, "matches_played": 0, "matches": []}
    return {
        "available": True, "team": team_name, "matches_played": len(recent),
        "average_goals_scored": sum(x["scored"] for x in recent) / len(recent),
        "average_goals_conceded": sum(x["conceded"] for x in recent) / len(recent),
        "matches": recent,
    }


def _season_team_rates(history: list[dict[str, Any]]) -> dict[str, Any]:
    """Build season-to-date venue rates using only matches already in history."""
    home_rows = [row for row in history if row.get("venue") == "home"]
    away_rows = [row for row in history if row.get("venue") == "away"]
    if not home_rows or not away_rows:
        return {"available": False, "home_matches": len(home_rows), "away_matches": len(away_rows)}

    def average(rows: list[dict[str, Any]], key: str) -> float:
        return sum(float(row[key]) for row in rows) / len(rows)

    return {
        "available": True,
        "scored_home": average(home_rows, "scored"),
        "conceded_home": average(home_rows, "conceded"),
        "scored_away": average(away_rows, "scored"),
        "conceded_away": average(away_rows, "conceded"),
        "home_matches": len(home_rows),
        "away_matches": len(away_rows),
    }


def _historical_opponent_strengths(
    team_history: dict[tuple[str, int], list[dict[str, Any]]],
    league_id: str,
    league_baseline: float,
) -> dict[int, dict[str, float]]:
    """Estimate shrunk opponent indices using only results before the forecast date."""
    strengths = {}
    for (history_league, team_id), history in team_history.items():
        if history_league != league_id or not history:
            continue
        count = len(history)
        attack_rate = sum(row["scored"] for row in history) / count
        defence_rate = sum(row["conceded"] for row in history) / count
        shrink = count / (count + 5.0)
        strengths[team_id] = {
            "attack_index": 1.0 + (attack_rate / league_baseline - 1.0) * shrink,
            "defence_index": 1.0 + (defence_rate / league_baseline - 1.0) * shrink,
        }
    return strengths


def _no_vig_1x2(odds: dict[str, Any] | None) -> dict[str, float] | None:
    """Normalize a complete same-source 1X2 price triplet to no-vig probabilities."""
    if not odds:
        return None
    try:
        inverse = {key: 1.0 / float(odds[key]) for key in ("home", "draw", "away")}
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None
    if not all(math.isfinite(value) and value > 0 for value in inverse.values()):
        return None
    overround = sum(inverse.values())
    if overround <= 0:
        return None
    return {key: value / overround for key, value in inverse.items()}


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
    team_history: dict[tuple[str, int], list[dict[str, Any]]] = {}
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
                strengths = _historical_opponent_strengths(team_history, league_id, league_baseline)
                home_venue = [row for row in home_hist if row.get("venue") == "home"]
                away_venue = [row for row in away_hist if row.get("venue") == "away"]
                home_source = home_venue if len(home_venue) >= 3 else home_hist
                away_source = away_venue if len(away_venue) >= 3 else away_hist
                home_form = adjust_recent_form_for_opponents(
                    _form(home_source, "home", history_window), strengths
                )
                away_form = adjust_recent_form_for_opponents(
                    _form(away_source, "away", history_window), strengths
                )
                home_season_rates = _season_team_rates(home_hist)
                away_season_rates = _season_team_rates(away_hist)
                forecast = forecast_from_recent_form(
                    home_form, away_form,
                    home_team_rates=home_season_rates,
                    away_team_rates=away_season_rates,
                    league_baseline=league_baseline,
                    home_advantage=home_advantage,
                )
                if forecast.get("available"):
                    probabilities = forecast["market_probabilities"]
                    actual_result = "home_win" if hg > ag else "away_win" if hg < ag else "draw"
                    historical_odds = item.get("historical_odds") or {}
                    market_probabilities = _no_vig_1x2(historical_odds)
                    predictions.append({
                        "fixture_id": (item.get("fixture") or {}).get("id"),
                        "date": date_value, "league_id": league_id,
                        "probabilities": probabilities,
                        "market_probabilities": market_probabilities,
                        "historical_odds_source": historical_odds.get("source"),
                        "historical_odds_timing": historical_odds.get("odds_timing"),
                        "model_method": forecast.get("method") or (forecast.get("goal_rates") or {}).get("method"),
                        "goal_rates": forecast.get("goal_rates"),
                        "season_rates_available": bool(home_season_rates.get("available") and away_season_rates.get("available")),
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
            date_value = _fixture_parts(_item)[0]
            team_history.setdefault((league_id, home_id), []).append({
                "date": date_value, "scored": hg, "conceded": ag,
                "opponent_id": away_id, "venue": "home",
            })
            team_history.setdefault((league_id, away_id), []).append({
                "date": date_value, "scored": ag, "conceded": hg,
                "opponent_id": home_id, "venue": "away",
            })
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
    market_rows = [row for row in predictions if row.get("market_probabilities")]
    market_comparison = None
    if market_rows:
        model_market_ll = []
        closing_market_ll = []
        model_market_brier = []
        closing_market_brier = []
        for row in market_rows:
            model_probs = row["probabilities"]
            market_probs = row["market_probabilities"]
            actual = row["actual_result"]
            model_market_ll.append(-_safe_log(model_probs[actual]))
            closing_market_ll.append(-_safe_log(market_probs[actual]))
            model_market_brier.append(sum(
                (model_probs[key] - (1.0 if key == actual else 0.0)) ** 2
                for key in ("home_win", "draw", "away_win")
            ))
            closing_market_brier.append(sum(
                (market_probs[key] - (1.0 if key == actual else 0.0)) ** 2
                for key in ("home", "draw", "away")
            ))
        market_n = len(market_rows)
        model_ll_market_sample = sum(model_market_ll) / market_n
        market_ll = sum(closing_market_ll) / market_n
        model_brier_market_sample = sum(model_market_brier) / market_n
        market_brier = sum(closing_market_brier) / market_n
        source_counts: dict[str, int] = {}
        timing_counts: dict[str, int] = {}
        for row in market_rows:
            source = row.get("historical_odds_source") or "unknown"
            timing = row.get("historical_odds_timing") or "unknown"
            source_counts[source] = source_counts.get(source, 0) + 1
            timing_counts[timing] = timing_counts.get(timing, 0) + 1
        market_comparison = {
            "matches_compared": market_n,
            "odds_coverage": f"{market_n}/{n}",
            "model_log_loss": model_ll_market_sample,
            "market_no_vig_log_loss": market_ll,
            "model_minus_market_log_loss": model_ll_market_sample - market_ll,
            "model_brier": model_brier_market_sample,
            "market_no_vig_brier": market_brier,
            "model_minus_market_brier": model_brier_market_sample - market_brier,
            "odds_source_counts": source_counts,
            "odds_timing_counts": timing_counts,
            "interpretation": "Positive model_minus_market values mean the model scores worse than the no-vig market.",
        }
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
        "market_comparison": market_comparison,
        "profitability_evaluated": False,
        "odds_coverage": len(market_rows),
        "odds_coverage_total": n,
        "odds_coverage_rate": len(market_rows) / n if n else 0.0,
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
