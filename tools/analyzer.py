"""Aggregated match analysis tool."""
from __future__ import annotations
import asyncio
from datetime import datetime
from typing import Any
from api_client import api_request, _error_response
from server import mcp
from tools.poisson_model import (
    extract_team_rates, extract_league_goal_baseline, forecast_from_recent_form,
)


def _summarize_team_form(team_id: int, team_name: str, result: dict[str, Any]) -> dict[str, Any]:
    """Summarize the last five finished matches for a team."""
    if not result.get("success"):
        return {"available": False, "team": team_name, "error": result.get("error", "Could not load team form.")}
    matches = result.get("data") or []
    finished = [item for item in matches if item.get("fixture", {}).get("status", {}).get("short") in ("FT", "AET", "PEN")]
    finished.sort(key=lambda item: item.get("fixture", {}).get("date") or "")
    summary = []
    wins = draws = losses = 0
    goals_for = goals_against = 0
    for item in finished:
        teams = item.get("teams") or {}
        home, away = teams.get("home") or {}, teams.get("away") or {}
        goals = item.get("goals") or {}
        hg, ag = goals.get("home"), goals.get("away")
        if hg is None or ag is None:
            continue
        if home.get("id") == team_id:
            scored, conceded, opponent, venue = hg, ag, away.get("name"), "home"
        elif away.get("id") == team_id:
            scored, conceded, opponent, venue = ag, hg, home.get("name"), "away"
        else:
            continue
        if scored > conceded:
            outcome = "W"; wins += 1
        elif scored == conceded:
            outcome = "D"; draws += 1
        else:
            outcome = "L"; losses += 1
        goals_for += scored; goals_against += conceded
        summary.append({
            "date": item.get("fixture", {}).get("date"), "opponent": opponent,
            "venue": venue, "score": f"{scored}-{conceded}", "result": outcome,
        })
    count = len(summary)
    return {
        "available": count > 0, "team": team_name, "matches_played": count,
        "form": "".join(item["result"] for item in summary),
        "wins": wins, "draws": draws, "losses": losses,
        "goals_scored": goals_for, "goals_conceded": goals_against,
        "average_goals_scored": round(goals_for / count, 2) if count else None,
        "average_goals_conceded": round(goals_against / count, 2) if count else None,
        "matches": summary,
    }


def _season_for_fixture(date_value: str | None) -> int | None:
    """API-Football season year: season starts in July."""
    if not date_value:
        return None
    try:
        kickoff = datetime.fromisoformat(date_value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return kickoff.year if kickoff.month >= 7 else kickoff.year - 1


@mcp.tool()
async def analyze_match(fixture_id: int) -> dict[str, Any]:
    """Collect fixture, recent form, team season splits and league baseline."""
    if not fixture_id or fixture_id <= 0:
        return _error_response("A valid fixture_id is required.")
    match_result = await api_request("/fixtures", {"ids": str(fixture_id)})
    if not match_result.get("success"):
        return {"success": False, "stage": "data_collection", "error": match_result.get("error", "Could not load match data.")}
    matches = match_result.get("data") or []
    if not matches:
        return _error_response("Fixture not found.")
    match = matches[0]
    teams = match.get("teams") or {}
    home, away = teams.get("home") or {}, teams.get("away") or {}
    home_id, away_id = home.get("id"), away.get("id")
    if not home_id or not away_id:
        return _error_response("Could not identify both teams in the fixture.")
    league = match.get("league") or {}
    league_id = league.get("id")
    season = league.get("season") or _season_for_fixture(match.get("fixture", {}).get("date"))

    requests = [
        api_request("/fixtures", {"team": home_id, "last": 5}),
        api_request("/fixtures", {"team": away_id, "last": 5}),
    ]
    if league_id and season:
        requests.extend([
            api_request("/teams/statistics", {"team": home_id, "league": league_id, "season": season}),
            api_request("/teams/statistics", {"team": away_id, "league": league_id, "season": season}),
            api_request("/standings", {"league": league_id, "season": season}),
        ])
    collected = await asyncio.gather(*requests)
    home_form = _summarize_team_form(home_id, home.get("name", "Home team"), collected[0])
    away_form = _summarize_team_form(away_id, away.get("name", "Away team"), collected[1])

    home_team_rates = extract_team_rates(collected[2]) if len(collected) >= 5 else {"available": False}
    away_team_rates = extract_team_rates(collected[3]) if len(collected) >= 5 else {"available": False}
    league_rates = extract_league_goal_baseline(collected[4]) if len(collected) >= 5 else {"available": False}
    league_baseline = league_rates.get("goals_per_team_match") if league_rates.get("available") else None
    forecast = forecast_from_recent_form(
        home_form, away_form, home_team_rates=home_team_rates,
        away_team_rates=away_team_rates, league_baseline=league_baseline,
    )
    full_data = bool(len(collected) >= 5 and home_team_rates.get("available") and away_team_rates.get("available") and league_baseline)
    return {
        "success": True,
        "analysis_status": "LEAGUE_ADJUSTED" if full_data else ("DATA_COLLECTION_WITH_FORM" if home_form.get("available") and away_form.get("available") else "PARTIAL_DATA_COLLECTION"),
        "message": "Match data, recent form and available league/venue season statistics collected. Use predict_match_bet for price comparison.",
        "fixture": {
            "id": fixture_id, "date": match.get("fixture", {}).get("date"),
            "status": match.get("fixture", {}).get("status"),
            "venue": match.get("fixture", {}).get("venue"), "league": league,
            "teams": teams, "goals": match.get("goals"), "score": match.get("score"),
        },
        "recent_form": {"home": home_form, "away": away_form},
        "season_statistics": {"home": home_team_rates, "away": away_team_rates, "league_baseline": league_rates},
        "forecast": forecast,
        "rate_limit_remaining": collected[-1].get("rate_limit_remaining") if collected else None,
    }
