"""Aggregated match analysis tool."""

from __future__ import annotations

import asyncio
from typing import Any

from api_client import api_request, _error_response
from server import mcp

def _summarize_team_form(
    team_id: int,
    team_name: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Summarize the last five finished matches for a team."""

    if not result.get("success"):
        return {
            "available": False,
            "team": team_name,
            "error": result.get("error", "Could not load team form."),
        }

    matches = result.get("data") or []

    finished = [
        item for item in matches
        if item.get("fixture", {}).get("status", {}).get("short")
        in ("FT", "AET", "PEN")
    ]

    finished.sort(
        key=lambda item: item.get("fixture", {}).get("date") or ""
    )

    summary = []
    wins = draws = losses = 0
    goals_for = goals_against = 0

    for item in finished:
        teams = item.get("teams") or {}
        home = teams.get("home") or {}
        away = teams.get("away") or {}
        goals = item.get("goals") or {}

        home_goals = goals.get("home")
        away_goals = goals.get("away")

        if home_goals is None or away_goals is None:
            continue

        if home.get("id") == team_id:
            scored = home_goals
            conceded = away_goals
            opponent = away.get("name")
            venue = "home"
        elif away.get("id") == team_id:
            scored = away_goals
            conceded = home_goals
            opponent = home.get("name")
            venue = "away"
        else:
            continue

        if scored > conceded:
            outcome = "W"
            wins += 1
        elif scored == conceded:
            outcome = "D"
            draws += 1
        else:
            outcome = "L"
            losses += 1

        goals_for += scored
        goals_against += conceded

        summary.append({
            "date": item.get("fixture", {}).get("date"),
            "opponent": opponent,
            "venue": venue,
            "score": f"{scored}-{conceded}",
            "result": outcome,
        })

    count = len(summary)

    return {
        "available": count > 0,
        "team": team_name,
        "matches_played": count,
        "form": "".join(item["result"] for item in summary),
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "goals_scored": goals_for,
        "goals_conceded": goals_against,
        "average_goals_scored": round(goals_for / count, 2) if count else None,
        "average_goals_conceded": round(goals_against / count, 2) if count else None,
        "matches": summary,
    }

@mcp.tool()
async def analyze_match(fixture_id: int) -> dict[str, Any]:
    """Collect match data and recent form using up to three API requests."""

    if not fixture_id or fixture_id <= 0:
        return _error_response("A valid fixture_id is required.")

    match_result = await api_request(
        "/fixtures",
        {"ids": str(fixture_id)},
    )

    if not match_result.get("success"):
        return {
            "success": False,
            "stage": "data_collection",
            "error": match_result.get("error", "Could not load match data."),
        }

    matches = match_result.get("data") or []

    if not matches:
        return _error_response("Fixture not found.")

    match = matches[0]
    teams = match.get("teams") or {}
    home = teams.get("home") or {}
    away = teams.get("away") or {}

    home_id = home.get("id")
    away_id = away.get("id")

    if not home_id or not away_id:
        return _error_response("Could not identify both teams in the fixture.")

    home_form_result, away_form_result = await asyncio.gather(
        api_request("/fixtures", {"team": home_id, "last": 5}),
        api_request("/fixtures", {"team": away_id, "last": 5}),
    )

    home_form = _summarize_team_form(
        home_id,
        home.get("name", "Home team"),
        home_form_result,
    )

    away_form = _summarize_team_form(
        away_id,


away.get("name", "Away team"),
        away_form_result,
    )

    both_forms_available = (
        home_form.get("available") and away_form.get("available")
    )

    return {
        "success": True,
        "analysis_status": (
            "DATA_COLLECTION_WITH_FORM"
            if both_forms_available
            else "PARTIAL_DATA_COLLECTION"
        ),
        "message": (
            "Match data and recent team form collected. "
            "Probability and betting value calculations are not yet implemented."
        ),
        "fixture": {
            "id": fixture_id,
            "date": match.get("fixture", {}).get("date"),
            "status": match.get("fixture", {}).get("status"),
            "venue": match.get("fixture", {}).get("venue"),
            "league": match.get("league"),
            "teams": teams,
            "goals": match.get("goals"),
            "score": match.get("score"),
        },
        "recent_form": {
            "home": home_form,
            "away": away_form,
        },
        "rate_limit_remaining": away_form_result.get(
            "rate_limit_remaining"
        ),
    }





