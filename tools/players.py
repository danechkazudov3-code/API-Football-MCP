"""Player tools: info, squads, seasons, top scorers/assists/cards."""

from __future__ import annotations

from api_client import api_request, require_params, _error_response

import sys
sys.path.insert(0, ".")
from server import mcp


@mcp.tool()
async def get_players(
    id: int | None = None,
    team: int | None = None,
    league: int | None = None,
    season: int | None = None,
    search: str | None = None,
    page: int | None = None,
) -> dict:
    """Get player information and statistics.

    Args:
        id: Player ID (if known)
        team: Team ID — filter by team (requires season)
        league: League ID — filter by league (requires season)
        season: Season year (required with team, league, or search)
        search: Player name search (min 3 chars, requires league or team + season)
        page: Page number for paginated results (20 per page)

    IMPORTANT: The 'search' parameter requires either 'league' or 'team' along with 'season'.
    Use search_player for a simpler name-based lookup.

    Returns player details (name, age, nationality, photo) and season statistics
    (appearances, goals, assists, cards, etc.) grouped by competition.
    """
    return await api_request("/players", {
        "id": id, "team": team, "league": league,
        "season": season, "search": search, "page": page,
    })


@mcp.tool()
async def get_player_squads(
    team: int | None = None,
    player: int | None = None,
) -> dict:
    """Get current squad for a team, or find which team a player belongs to.

    Args:
        team: Team ID — get the full squad roster
        player: Player ID — find which team this player is on

    At least one parameter required. Returns player details including
    name, age, number, position, and photo.
    """
    return await api_request("/players/squads", {"team": team, "player": player})


@mcp.tool()
async def get_player_seasons(player: int) -> dict:
    """Get all available seasons for a specific player.

    Args:
        player: Player ID (required)

    Returns a list of season years the player has data for.
    """
    err = require_params(["player"], {"player": player})
    if err:
        return _error_response(err)
    return await api_request("/players/seasons", {"player": player})


@mcp.tool()
async def get_top_scorers(league: int, season: int) -> dict:
    """Get top goal scorers for a league and season.

    Args:
        league: League ID (required)
        season: Season year (required, e.g., 2024)

    Returns top 20 scorers with player details and goal tallies.
    """
    err = require_params(["league", "season"], {"league": league, "season": season})
    if err:
        return _error_response(err)
    return await api_request("/players/topscorers", {"league": league, "season": season})


@mcp.tool()
async def get_top_assists(league: int, season: int) -> dict:
    """Get top assist providers for a league and season.

    Args:
        league: League ID (required)
        season: Season year (required, e.g., 2024)

    Returns top 20 assist providers with player details.
    """
    err = require_params(["league", "season"], {"league": league, "season": season})
    if err:
        return _error_response(err)
    return await api_request("/players/topassists", {"league": league, "season": season})


@mcp.tool()
async def get_top_yellow_cards(league: int, season: int) -> dict:
    """Get players with most yellow cards in a league and season.

    Args:
        league: League ID (required)
        season: Season year (required, e.g., 2024)

    Returns top 20 players by yellow cards.
    """
    err = require_params(["league", "season"], {"league": league, "season": season})
    if err:
        return _error_response(err)
    return await api_request("/players/topyellowcards", {"league": league, "season": season})


@mcp.tool()
async def get_top_red_cards(league: int, season: int) -> dict:
    """Get players with most red cards in a league and season.

    Args:
        league: League ID (required)
        season: Season year (required, e.g., 2024)

    Returns top 20 players by red cards.
    """
    err = require_params(["league", "season"], {"league": league, "season": season})
    if err:
        return _error_response(err)
    return await api_request("/players/topredcards", {"league": league, "season": season})


@mcp.tool()
async def get_player_profiles(
    player: int | None = None,
    search: str | None = None,
    page: int | None = None,
) -> dict:
    """Get player profiles (bio only, no statistics) across all leagues and seasons.

    Args:
        player: Player ID
        search: Player last name (min 4 chars) — no league/team/season needed
        page: Page number (250 results per page)

    Unlike get_players, searching here does not require a league, team or season.
    Returns player name, first/last name, age, birth date/place, nationality,
    height, weight, number, position, and photo.
    """
    if search is not None and len(search) < 4:
        return _error_response("Search term must be at least 4 characters long.")
    return await api_request("/players/profiles", {
        "player": player, "search": search, "page": page,
    })


@mcp.tool()
async def get_player_teams(player: int) -> dict:
    """Get every team a player has played for during their career, with the seasons at each.

    Args:
        player: Player ID (required)

    Returns list of {team: {id, name, logo}, seasons: [YYYY, ...]}.
    """
    err = require_params(["player"], {"player": player})
    if err:
        return _error_response(err)
    return await api_request("/players/teams", {"player": player})
