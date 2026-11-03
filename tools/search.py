"""Convenience search/name-resolution tools.

These tools make it easy to find IDs by searching names, which is the most
common first step when using the API.
"""

from __future__ import annotations

from api_client import api_request, current_season, require_params, _error_response

import sys
sys.path.insert(0, ".")
from server import mcp


@mcp.tool()
async def search_team(name: str) -> dict:
    """Search for a football team by name and get its ID.

    Args:
        name: Team name to search for (min 3 chars, e.g., 'Manchester', 'Barcelona', 'Bayern')

    Returns matching teams with their IDs, full names, countries, logos, and venues.
    Use the returned team ID in other tools like get_team_statistics, get_fixtures, etc.

    Example: search_team('Liverpool') → team ID 40
    """
    err = require_params(["name"], {"name": name})
    if err:
        return _error_response(err)
    if len(name) < 3:
        return _error_response("Search term must be at least 3 characters long.")

    result = await api_request("/teams", {"search": name})
    if not result.get("success"):
        return result

    # Simplify output for easier consumption
    teams = []
    for item in result.get("data", []):
        team_info = item.get("team", {})
        venue_info = item.get("venue", {})
        teams.append({
            "id": team_info.get("id"),
            "name": team_info.get("name"),
            "code": team_info.get("code"),
            "country": team_info.get("country"),
            "founded": team_info.get("founded"),
            "logo": team_info.get("logo"),
            "venue": venue_info.get("name"),
            "venue_city": venue_info.get("city"),
            "venue_capacity": venue_info.get("capacity"),
        })

    return {
        "success": True,
        "results": len(teams),
        "data": teams,
        "rate_limit_remaining": result.get("rate_limit_remaining"),
    }


@mcp.tool()
async def search_player(
    name: str,
    league: int | None = None,
    team: int | None = None,
    season: int | None = None,
) -> dict:
    """Search for a football player by name and get their ID.

    Args:
        name: Player name to search for (min 4 chars, e.g., 'Haaland', 'Messi', 'Salah')
        league: League ID to search within (optional)
        team: Team ID to search within (optional, alternative to league)
        season: Season year with league/team (defaults to the current season)

    Without league or team, searches all player profiles by last name (no team info
    in that mode — use get_player_squads or get_player_teams for it).
    With league or team, searches that competition/team for the season and includes team.
    Common league IDs: 39=Premier League, 140=La Liga, 135=Serie A, 78=Bundesliga, 61=Ligue 1.

    Returns matching players with IDs, names, ages, nationalities, and current team.

    Example: search_player('Haaland') or search_player('Haaland', league=39) → player ID 1100
    """
    err = require_params(["name"], {"name": name})
    if err:
        return _error_response(err)
    if len(name) < 4:
        return _error_response("Search term must be at least 4 characters long.")

    if league is None and team is None:
        result = await api_request("/players/profiles", {"search": name})
        if not result.get("success"):
            return result
        players = []
        for item in result.get("data", []):
            p = item.get("player", {})
            players.append({
                "id": p.get("id"),
                "name": p.get("name"),
                "firstname": p.get("firstname"),
                "lastname": p.get("lastname"),
                "age": p.get("age"),
                "nationality": p.get("nationality"),
                "position": p.get("position"),
                "photo": p.get("photo"),
            })
        return {
            "success": True,
            "results": len(players),
            "data": players,
            "paging": result.get("paging", {}),
            "rate_limit_remaining": result.get("rate_limit_remaining"),
        }

    if season is None:
        season = current_season()

    result = await api_request("/players", {
        "search": name, "league": league, "team": team, "season": season,
    })
    if not result.get("success"):
        return result

    # Simplify output
    players = []
    for item in result.get("data", []):
        player_info = item.get("player", {})
        stats = item.get("statistics", [])
        current_team = stats[0].get("team", {}) if stats else {}
        players.append({
            "id": player_info.get("id"),
            "name": player_info.get("name"),
            "firstname": player_info.get("firstname"),
            "lastname": player_info.get("lastname"),
            "age": player_info.get("age"),
            "nationality": player_info.get("nationality"),
            "photo": player_info.get("photo"),
            "team_id": current_team.get("id"),
            "team_name": current_team.get("name"),
        })

    return {
        "success": True,
        "results": len(players),
        "data": players,
        "paging": result.get("paging", {}),
        "rate_limit_remaining": result.get("rate_limit_remaining"),
    }


@mcp.tool()
async def search_league(name: str) -> dict:
    """Search for a league/competition by name and get its ID.

    Args:
        name: League name to search for (min 3 chars, e.g., 'Premier', 'Champions', 'Liga')

    Returns matching leagues with IDs, names, countries, types, and available seasons.
    Use the returned league ID in other tools like get_standings, get_fixtures, etc.

    Example: search_league('Premier League') → league ID 39
    """
    err = require_params(["name"], {"name": name})
    if err:
        return _error_response(err)
    if len(name) < 3:
        return _error_response("Search term must be at least 3 characters long.")

    result = await api_request("/leagues", {"search": name})
    if not result.get("success"):
        return result

    leagues = []
    for item in result.get("data", []):
        league_info = item.get("league", {})
        country_info = item.get("country", {})
        seasons = item.get("seasons", [])
        available_seasons = [s.get("year") for s in seasons] if seasons else []
        leagues.append({
            "id": league_info.get("id"),
            "name": league_info.get("name"),
            "type": league_info.get("type"),
            "country": country_info.get("name"),
            "country_code": country_info.get("code"),
            "logo": league_info.get("logo"),
            "seasons": available_seasons[-5:] if len(available_seasons) > 5 else available_seasons,
        })

    return {
        "success": True,
        "results": len(leagues),
        "data": leagues,
        "rate_limit_remaining": result.get("rate_limit_remaining"),
    }


@mcp.tool()
async def search_coach(name: str) -> dict:
    """Search for a coach/manager by name and get their ID.

    Args:
        name: Coach name to search for (min 3 chars, e.g., 'Guardiola', 'Klopp', 'Ancelotti')

    Returns matching coaches with IDs, names, nationalities, and current/past teams.

    Example: search_coach('Guardiola') → coach ID 4
    """
    err = require_params(["name"], {"name": name})
    if err:
        return _error_response(err)
    if len(name) < 3:
        return _error_response("Search term must be at least 3 characters long.")

    result = await api_request("/coachs", {"search": name})
    if not result.get("success"):
        return result

    coaches = []
    for item in result.get("data", []):
        career = item.get("career", [])
        current_team = None
        for c in career:
            if c.get("end") is None:
                current_team = c.get("team", {}).get("name")
                break
        coaches.append({
            "id": item.get("id"),
            "name": item.get("name"),
            "firstname": item.get("firstname"),
            "lastname": item.get("lastname"),
            "age": item.get("age"),
            "nationality": item.get("nationality"),
            "photo": item.get("photo"),
            "current_team": current_team,
        })

    return {
        "success": True,
        "results": len(coaches),
        "data": coaches,
        "rate_limit_remaining": result.get("rate_limit_remaining"),
    }


@mcp.tool()
async def search_venue(name: str) -> dict:
    """Search for a stadium/venue by name and get its ID.

    Args:
        name: Venue name to search for (min 3 chars, e.g., 'Old Trafford', 'Bernabeu', 'Anfield')

    Returns matching venues with IDs, names, cities, countries, and capacities.

    Example: search_venue('Old Trafford') → venue ID 556
    """
    err = require_params(["name"], {"name": name})
    if err:
        return _error_response(err)
    if len(name) < 3:
        return _error_response("Search term must be at least 3 characters long.")

    result = await api_request("/venues", {"search": name})
    if not result.get("success"):
        return result

    venues = []
    for item in result.get("data", []):
        venues.append({
            "id": item.get("id"),
            "name": item.get("name"),
            "city": item.get("city"),
            "country": item.get("country"),
            "capacity": item.get("capacity"),
            "surface": item.get("surface"),
            "address": item.get("address"),
        })

    return {
        "success": True,
        "results": len(venues),
        "data": venues,
        "rate_limit_remaining": result.get("rate_limit_remaining"),
    }
