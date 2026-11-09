"""MCP workflow for live match state, live statistics and in-play odds."""
from __future__ import annotations
import asyncio
from typing import Any
from api_client import api_request
from server import mcp
from tools.analyzer import analyze_match
from tools.live_model import estimate_remaining_goal_rates, derive_live_probabilities
from tools.prediction import evaluate_candidate, select_primary_candidate
from tools.recommendation import extract_best_prices


LIVE_STATUSES = {"1H", "HT", "2H", "ET", "BT", "LIVE"}


def _number(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(str(value).replace("%", "").strip())
    except (TypeError, ValueError):
        return 0.0


def _live_stats(response: dict[str, Any], home_id: int, away_id: int) -> dict[str, float]:
    values = {
        home_id: {"shots": 0.0, "sot": 0.0},
        away_id: {"shots": 0.0, "sot": 0.0},
    }
    if not response.get("success"):
        return {"shots_home": 0, "shots_away": 0, "sot_home": 0, "sot_away": 0}
    for team_stats in response.get("data") or []:
        team_id = (team_stats.get("team") or {}).get("id")
        if team_id not in values:
            continue
        for stat in team_stats.get("statistics") or []:
            name = str(stat.get("type") or "").lower()
            if name == "total shots":
                values[team_id]["shots"] = _number(stat.get("value"))
            elif name in {"shots on goal", "shots on target"}:
                values[team_id]["sot"] = _number(stat.get("value"))
    return {
        "shots_home": values[home_id]["shots"], "shots_away": values[away_id]["shots"],
        "sot_home": values[home_id]["sot"], "sot_away": values[away_id]["sot"],
    }


def _red_cards(response: dict[str, Any], home_id: int, away_id: int) -> tuple[int, int]:
    home_red = away_red = 0
    if not response.get("success"):
        return home_red, away_red
    for event in response.get("data") or []:
        if str(event.get("type") or "").lower() != "card":
            continue
        detail = str(event.get("detail") or "").lower()
        if "red" not in detail and "second yellow" not in detail:
            continue
        team_id = (event.get("team") or {}).get("id")
        if team_id == home_id:
            home_red += 1
        elif team_id == away_id:
            away_red += 1
    return home_red, away_red


@mcp.tool()
async def predict_live_match_bet(fixture_id: int) -> dict[str, Any]:
    """Automatically evaluate a live match using remaining-time probabilities."""
    analysis = await analyze_match(fixture_id)
    if not analysis.get("success"):
        return {"success": False, "mode": "LIVE", "error": analysis.get("error", "Match analysis failed.")}
    fixture = analysis.get("fixture") or {}
    status = fixture.get("status") or {}
    status_short = status.get("short")
    if status_short not in LIVE_STATUSES:
        return {
            "success": True, "mode": "LIVE", "status": "INSUFFICIENT_DATA",
            "fixture": fixture, "primary_pick": None, "candidates": [],
            "reason": "Fixture is not currently in a supported live state.",
        }
    elapsed = status.get("elapsed")
    score = fixture.get("goals") or {}
    home_goals, away_goals = score.get("home"), score.get("away")
    teams = fixture.get("teams") or {}
    home_id = (teams.get("home") or {}).get("id")
    away_id = (teams.get("away") or {}).get("id")
    rates = ((analysis.get("forecast") or {}).get("goal_rates") or {})
    if elapsed is None or home_goals is None or away_goals is None or not rates.get("available"):
        return {
            "success": True, "mode": "LIVE", "status": "INSUFFICIENT_DATA",
            "fixture": fixture, "primary_pick": None, "candidates": [],
            "reason": "Live minute, score or pre-match goal-rate baseline is unavailable.",
        }

    stats_response, events_response, odds_response = await asyncio.gather(
        api_request("/fixtures/statistics", {"fixture": fixture_id}),
        api_request("/fixtures/events", {"fixture": fixture_id}),
        api_request("/odds/live", {"fixture": fixture_id}),
    )
    live_stats = _live_stats(stats_response, home_id, away_id)
    red_home, red_away = _red_cards(events_response, home_id, away_id)
    remaining = estimate_remaining_goal_rates(
        rates["lambda_home"], rates["lambda_away"], int(elapsed),
        shots_home=live_stats["shots_home"], shots_away=live_stats["shots_away"],
        shots_on_target_home=live_stats["sot_home"], shots_on_target_away=live_stats["sot_away"],
        red_cards_home=red_home, red_cards_away=red_away,
        regulation_end_minute=125 if status_short in {"ET", "BT"} else 95,
    )
    probabilities = derive_live_probabilities(
        remaining["lambda_home_remaining"], remaining["lambda_away_remaining"],
        int(home_goals), int(away_goals),
    )
    best_prices = extract_best_prices(odds_response)
    labels = {
        "home_win": ("1X2", "Home win"), "draw": ("1X2", "Draw"),
        "away_win": ("1X2", "Away win"),
        "over_2_5": ("Total goals 2.5", "Over 2.5"),
        "under_2_5": ("Total goals 2.5", "Under 2.5"),
        "btts_yes": ("Both teams to score", "Yes"),
        "btts_no": ("Both teams to score", "No"),
    }
    candidates = []
    for key, probability in probabilities.items():
        market, selection = labels[key]
        candidate = {
            "market": market, "selection": selection,
            "model_probability": round(probability, 6),
            "odds": None, "mode": "LIVE",
        }
        price = best_prices.get(key)
        if price:
            candidate.update(price)
        candidates.append(evaluate_candidate(candidate, model_validated=False))
    primary = select_primary_candidate(candidates)
    return {
        "success": True, "mode": "LIVE",
        "status": primary.get("status") if primary else "INSUFFICIENT_DATA",
        "fixture": fixture, "primary_pick": primary, "candidates": candidates,
        "live_state": {
            "elapsed": elapsed, "score": {"home": home_goals, "away": away_goals},
            "statistics": live_stats, "red_cards": {"home": red_home, "away": red_away},
        },
        "remaining_goal_model": remaining,
        "model_validated": False,
        "odds_available": bool(best_prices),
        "warning": "Experimental in-play baseline. Live statistics and odds may be incomplete or delayed; not calibrated or backtested.",
    }
