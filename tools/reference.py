"""Reference data tools: timezones, countries, seasons, leagues."""

from __future__ import annotations

from api_client import api_request

# Import mcp from server module
import sys
sys.path.insert(0, ".")
from server import mcp


@mcp.tool()
async def get_timezones() -> dict:
    """Get all available timezones supported by API-Football.

    Returns a list of timezone strings (e.g., 'Europe/London', 'America/New_York').
    Useful for specifying timezone in fixture queries.
    """
    return await api_request("/timezone")


@mcp.tool()
async def get_countries(
    name: str | None = None,
    code: str | None = None,
    search: str | None = None,
) -> dict:
    """Get countries available in API-Football.

    Args:
        name: Exact country name (e.g., 'England', 'France')
        code: Country code (e.g., 'GB', 'FR')
        search: Search term (min 3 chars) to find countries by name

    Returns list of countries with name, code, and flag URL.
    """
    return await api_request("/countries", {"name": name, "code": code, "search": search})


@mcp.tool()
async def get_seasons() -> dict:
    """Get all available seasons in API-Football.

    Returns a list of years (e.g., [2010, 2011, ..., 2024]).
    Use these values as the 'season' parameter in other tools.
    """
    return await api_request("/leagues/seasons")


@mcp.tool()
async def get_leagues(
    id: int | None = None,
    name: str | None = None,
    country: str | None = None,
    code: str | None = None,
    season: int | None = None,
    team: int | None = None,
    search: str | None = None,
    type: str | None = None,
    current: str | None = None,
    last: int | None = None,
) -> dict:
    """Get league/competition information.

    Args:
        id: League ID
        name: Exact league name
        country: Country name (e.g., 'England')
        code: Country code (e.g., 'GB')
        season: Season year (e.g., 2026)
        team: Team ID — leagues/cups this team has played in
        search: Search term (min 3 chars)
        type: 'league' or 'cup'
        current: 'true' or 'false' — only current leagues
        last: Number of last seasons to return

    Returns league details including name, country, seasons, and coverage info.
    """
    return await api_request("/leagues", {
        "id": id, "name": name, "country": country, "code": code,
        "season": season, "team": team, "search": search, "type": type,
        "current": current, "last": last,
    })


@mcp.tool()
async def get_api_status() -> dict:
    """Get API-Football account status: plan, subscription end date, and today's request usage.

    This call does not count against the daily quota.
    Returns subscription (plan, end, active) and requests (current, limit_day).
    """
    result = await api_request("/status")
    # Drop the account holder's name/email — the server is often exposed without auth.
    if result.get("success") and isinstance(result.get("data"), dict):
        result["data"].pop("account", None)
    return result
