"""Trophies tool: player and coach trophies."""

from __future__ import annotations

from api_client import api_request, require_at_least_one, _error_response

import sys
sys.path.insert(0, ".")
from server import mcp


@mcp.tool()
async def get_trophies(
    player: int | None = None,
    coach: int | None = None,
    players: str | None = None,
    coaches: str | None = None,
) -> dict:
    """Get trophies won by one or more players or coaches.

    Args:
        player: Player ID
        coach: Coach ID
        players: Several player IDs separated by dashes (e.g., '276-1460', max 20)
        coaches: Several coach IDs separated by dashes (e.g., '2-6', max 20)

    At least one parameter is required.
    Returns list of trophies with league/competition name, country, season,
    and place (Winner, Runner-up, etc.). With players/coaches, results are
    grouped per person ID.
    """
    values = {"player": player, "coach": coach, "players": players, "coaches": coaches}
    err = require_at_least_one(list(values), values)
    if err:
        return _error_response(err)
    return await api_request("/trophies", {
        "player": player, "coach": coach, "players": players, "coachs": coaches,
    })
