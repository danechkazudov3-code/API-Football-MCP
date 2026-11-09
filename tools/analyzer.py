"""Aggregated matchup-first analysis for a single football fixture."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from api_client import api_request, _error_response
from server import mcp
from tools.poisson_model import (
    extract_team_rates,
    extract_league_goal_baseline,
    forecast_from_recent_form,
)


FINISHED = {"FT", "AET", "PEN"}


def _summarize_team_form(team_id: int, team_name: str, result: dict[str, Any]) -> dict[str, Any]:
    """Summarize up to ten recent finished matches, including home/away splits."""
    if not result.get("success"):
        return {"available": False, "team": team_name, "error": result.get("error", "Could not load team form.")}

    matches = result.get("data") or []
    finished = [
        item for item in matches
        if item.get("fixture", {}).get("status", {}).get("short") in FINISHED
    ]
    finished.sort(key=lambda item: item.get("fixture", {}).get("date") or "")

    summary: list[dict[str, Any]] = []
    splits: dict[str, list[tuple[int, int, str]]] = {
        "home": [], "away": [],
    }
    wins = draws = losses = goals_for = goals_against = 0

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
        splits[venue].append((scored, conceded, outcome))
        summary.append({
            "date": item.get("fixture", {}).get("date"),
            "opponent": opponent,
            "venue": venue,
            "score": f"{scored}-{conceded}",
            "result": outcome,
        })

    def split_summary(rows: list[tuple[int, int, str]]) -> dict[str, Any]:
        count = len(rows)
        return {
            "available": count > 0,
            "matches_played": count,
            "wins": sum(row[2] == "W" for row in rows),
            "draws": sum(row[2] == "D" for row in rows),
            "losses": sum(row[2] == "L" for row in rows),
            "average_goals_scored": round(sum(row[0] for row in rows) / count, 2) if count else None,
            "average_goals_conceded": round(sum(row[1] for row in rows) / count, 2) if count else None,
            "form": "".join(row[2] for row in rows),
        }

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
        "venue_splits": {
            "home": split_summary(splits["home"]),
            "away": split_summary(splits["away"]),
        },
        "matches": summary,
    }


def _summarize_head_to_head(result: dict[str, Any], home_team_id: int, away_team_id: int) -> dict[str, Any]:
    if not result.get("success"):
        return {"available": False, "error": result.get("error", "Head-to-head data unavailable.")}
    rows = [
        item for item in (result.get("data") or [])
        if item.get("fixture", {}).get("status", {}).get("short") in FINISHED
    ]
    rows.sort(key=lambda item: item.get("fixture", {}).get("date") or "", reverse=True)
    matches = []
    home_wins = draws = away_wins = 0
    for item in rows[:5]:
        teams, goals = item.get("teams") or {}, item.get("goals") or {}
        home, away = teams.get("home") or {}, teams.get("away") or {}
        hg, ag = goals.get("home"), goals.get("away")
        if hg is None or ag is None:
            continue
        current_home_goals = hg if home.get("id") == home_team_id else ag
        current_away_goals = ag if away.get("id") == away_team_id else hg
        if current_home_goals > current_away_goals:
            home_wins += 1
        elif current_home_goals == current_away_goals:
            draws += 1
        else:
            away_wins += 1
        matches.append({
            "date": (item.get("fixture") or {}).get("date"),
            "home": home.get("name"), "away": away.get("name"),
            "score": f"{hg}-{ag}",
        })
    return {
        "available": bool(matches),
        "matches_played": len(matches),
        "current_home_team_wins": home_wins,
        "draws": draws,
        "current_away_team_wins": away_wins,
        "matches": matches,
        "note": "Historical H2H is contextual evidence, not the primary form signal.",
    }


def _summarize_injuries(result: dict[str, Any]) -> dict[str, Any]:
    if not result.get("success"):
        return {"available": False, "error": result.get("error", "Injury data unavailable.")}
    rows = result.get("data") or []
    items = []
    for row in rows:
        player = row.get("player") or {}
        team = row.get("team") or {}
        items.append({
            "player": player.get("name"),
            "team": team.get("name"),
            "type": row.get("type"),
            "reason": row.get("reason"),
        })
    return {"available": True, "count": len(items), "items": items}


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
    """Analyze each team's recent form, venue splits, season rates, H2H and injuries."""
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
        api_request("/fixtures", {"team": home_id, "last": 10, "status": "FT-AET-PEN"}),
        api_request("/fixtures", {"team": away_id, "last": 10, "status": "FT-AET-PEN"}),
        api_request("/fixtures/headtohead", {"h2h": f"{home_id}-{away_id}", "last": 5, "status": "FT-AET-PEN"}),
        api_request("/injuries", {"fixture": fixture_id}),
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
    h2h = _summarize_head_to_head(collected[2], home_id, away_id)
    injuries = _summarize_injuries(collected[3])

    offset = 4
    if len(collected) >= 7:
        home_team_rates = extract_team_rates(collected[offset])
        away_team_rates = extract_team_rates(collected[offset + 1])
        league_rates = extract_league_goal_baseline(collected[offset + 2])
    else:
        home_team_rates = away_team_rates = {"available": False}
        league_rates = {"available": False}

    league_baseline = league_rates.get("goals_per_team_match") if league_rates.get("available") else None

    # Use venue-specific recent form when there is a minimally useful sample;
    # otherwise retain the larger all-venue sample rather than overfitting 1-2 games.
    home_venue = (home_form.get("venue_splits") or {}).get("home") or {}
    away_venue = (away_form.get("venue_splits") or {}).get("away") or {}
    model_home_form = home_venue if home_venue.get("matches_played", 0) >= 3 else home_form
    model_away_form = away_venue if away_venue.get("matches_played", 0) >= 3 else away_form

    forecast = forecast_from_recent_form(
        model_home_form,
        model_away_form,
        home_team_rates=home_team_rates,
        away_team_rates=away_team_rates,
        league_baseline=league_baseline,
    )
    full_data = bool(
        home_team_rates.get("available")
        and away_team_rates.get("available")
        and league_baseline
    )

    return {
        "success": True,
        "analysis_status": "LEAGUE_ADJUSTED" if full_data else (
            "DATA_COLLECTION_WITH_FORM" if home_form.get("available") and away_form.get("available")
            else "PARTIAL_DATA_COLLECTION"
        ),
        "message": (
            "Matchup analysis combines each team's last ten matches, home/away recent-form splits, "
            "season venue rates, H2H context and fixture injury information where available."
        ),
        "fixture": {
            "id": fixture_id,
            "date": match.get("fixture", {}).get("date"),
            "status": match.get("fixture", {}).get("status"),
            "venue": match.get("fixture", {}).get("venue"),
            "league": league,
            "teams": teams,
            "goals": match.get("goals"),
            "score": match.get("score"),
        },
        "recent_form": {
            "home": home_form,
            "away": away_form,
            "model_inputs": {
                "home": "recent_home_matches" if model_home_form is home_venue else "all_recent_matches",
                "away": "recent_away_matches" if model_away_form is away_venue else "all_recent_matches",
            },
        },
        "head_to_head": h2h,
        "injuries": injuries,
        "season_statistics": {
            "home": home_team_rates,
            "away": away_team_rates,
            "league_baseline": league_rates,
        },
        "forecast": forecast,
        "data_limitations": [
            "H2H and injury information are displayed as context; they are not yet numerical adjustments to the Poisson rates.",
            "Lineups are not confirmed until the provider publishes them.",
            "Season statistics may be unavailable on the current API plan; recent-form fallback is used instead.",
        ],
        "rate_limit_remaining": collected[-1].get("rate_limit_remaining") if collected else None,
    }
