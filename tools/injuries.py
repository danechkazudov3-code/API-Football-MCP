"""Injuries tool: current injuries."""

from __future__ import annotations

from api_client import api_request, require_at_least_one, _error_response

import sys
sys.path.insert(0, ".")
from server import mcp


@mcp.tool()
async def get_injuries(
    league: int | None = None,
    season: int | None = None,
    fixture: int | None = None,
    team: int | None = None,
    player: int | None = None,
    date: str | None = None,
    ids: str | None = None,
    timezone: str | None = None,
) -> dict:
    """Get injury information for players.

    Args:
        league: League ID (use with season)
        season: Season year (use with league, team, or player)
        fixture: Fixture ID to get injuries for a specific match
        team: Team ID
        player: Player ID
        date: Date (YYYY-MM-DD) to get injuries for a specific date
        ids: Several fixture IDs separated by dashes (e.g., '123-456', max 20)
        timezone: Timezone for date filtering

    At least one filter parameter should be provided.
    Returns player injury details: player name/photo, team, fixture,
    injury type, and reason.
    """
    values = {
        "league": league, "season": season, "fixture": fixture, "team": team,
        "player": player, "date": date, "ids": ids,
    }
    err = require_at_least_one(list(values), values)
    if err:
        return _error_response(err)
    if season is None and any(value is not None for value in (league, team, player)):
        return _error_response("The season parameter is required with league, team, or player.")
    return await api_request("/injuries", {
        "league": league, "season": season, "fixture": fixture,
        "team": team, "player": player, "date": date, "ids": ids,
        "timezone": timezone,
    })
