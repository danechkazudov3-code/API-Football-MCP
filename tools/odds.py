"""Odds tools: pre-match odds, live odds, bookmakers, bet types, mapping.

Odds responses from the API are very large (1MB+ per fixture unfiltered).
The tools here simplify and flatten responses to keep them manageable.
Always use the 'bet' parameter to filter by bet type when possible.
"""

from __future__ import annotations

from api_client import api_request, require_at_least_one, _error_response

import sys
sys.path.insert(0, ".")
from server import mcp


def _simplify_odds(result: dict) -> dict:
    """Flatten and simplify odds response to reduce size.

    Transforms the deeply nested API response into a compact format:
    - Strips league logos, country flags, and redundant metadata
    - Flattens bookmaker→bets→values into a clean structure
    """
    if not result.get("success") or not result.get("data"):
        return result

    simplified = []
    for entry in result["data"]:
        fixture_info = entry.get("fixture", {})
        league_info = entry.get("league", {})

        odds_by_bet = {}
        for bk in entry.get("bookmakers", []):
            bk_name = bk.get("name", "Unknown")
            bk_id = bk.get("id")
            for bet in bk.get("bets", []):
                bet_name = bet.get("name", "Unknown")
                bet_id = bet.get("id")
                key = f"{bet_id}:{bet_name}"
                if key not in odds_by_bet:
                    odds_by_bet[key] = {
                        "bet_id": bet_id,
                        "bet_name": bet_name,
                        "bookmakers": [],
                    }
                odds_by_bet[key]["bookmakers"].append({
                    "id": bk_id,
                    "name": bk_name,
                    "values": bet.get("values", []),
                })

        simplified.append({
            "fixture_id": fixture_info.get("id"),
            "date": fixture_info.get("date"),
            "league": league_info.get("name"),
            "league_id": league_info.get("id"),
            "update": entry.get("update"),
            "odds": list(odds_by_bet.values()),
        })

    return {
        "success": True,
        "results": len(simplified),
        "data": simplified,
        "paging": result.get("paging", {}),
        "rate_limit_remaining": result.get("rate_limit_remaining"),
    }


def _summarize_available_bets(result: dict) -> dict:
    """When no bet filter is set, return just a list of available bet type IDs and names.

    This avoids massive responses while telling the caller exactly what's available.
    """
    if not result.get("success") or not result.get("data"):
        return result

    summaries = []
    for entry in result["data"]:
        fixture_info = entry.get("fixture", {})
        league_info = entry.get("league", {})

        bet_types = {}
        for bk in entry.get("bookmakers", []):
            for bet in bk.get("bets", []):
                bid = bet.get("id")
                if bid not in bet_types:
                    bet_types[bid] = bet.get("name", "Unknown")

        summaries.append({
            "fixture_id": fixture_info.get("id"),
            "date": fixture_info.get("date"),
            "league": league_info.get("name"),
            "league_id": league_info.get("id"),
            "available_bets": [
                {"id": bid, "name": name}
                for bid, name in sorted(bet_types.items())
            ],
            "hint": "Call get_odds again with bet=<id> to get actual odds values.",
        })

    return {
        "success": True,
        "results": len(summaries),
        "data": summaries,
        "paging": result.get("paging", {}),
        "rate_limit_remaining": result.get("rate_limit_remaining"),
    }


def _simplify_live_odds(result: dict, bookmaker_name: str | None = None) -> dict:
    """Flatten live odds; preserve all returned bookmakers by default."""
    if not result.get("success") or not result.get("data"):
        return result

    simplified = []
    for entry in result["data"]:
        fixture_info = entry.get("fixture", {})
        league_info = entry.get("league", {})

        odds_list = []
        for bk in entry.get("bookmakers", []):
            bk_name = bk.get("name", "Unknown")
            if bookmaker_name and bk_name.lower() != bookmaker_name.lower():
                continue
            for bet in bk.get("bets", []):
                odds_list.append({
                    "bookmaker_id": bk.get("id"),
                    "bookmaker": bk_name,
                    "bet_id": bet.get("id"),
                    "bet_name": bet.get("name"),
                    "values": bet.get("values", []),
                })

        simplified.append({
            "fixture_id": fixture_info.get("id"),
            "status": fixture_info.get("status", {}).get("long"),
            "elapsed": fixture_info.get("status", {}).get("elapsed"),
            "league": league_info.get("name"),
            "league_id": league_info.get("id"),
            "update": entry.get("update"),
            "odds": odds_list,
        })

    return {
        "success": True,
        "results": len(simplified),
        "data": simplified,
        "paging": result.get("paging", {}),
        "rate_limit_remaining": result.get("rate_limit_remaining"),
    }


@mcp.tool()
async def get_odds(
    fixture: int | None = None,
    league: int | None = None,
    season: int | None = None,
    date: str | None = None,
    timezone: str | None = None,
    page: int | None = None,
    bookmaker: int = 8,
    bet: int | None = None,
) -> dict:
    """Get pre-match betting odds. Defaults to Bet365 only.

    When 'bet' is provided: returns full odds for that bet type.
    When 'bet' is omitted: returns a summary listing available bet types and their IDs,
    so you can then call again with a specific bet ID.

    Common bet type IDs:
        1 = Match Winner, 2 = Home/Away, 3 = Second Half Winner,
        5 = Goals Over/Under, 8 = Both Teams Score, 12 = Double Chance,
        17 = Asian Handicap, 26 = Correct Score

    Args:
        fixture: Fixture ID (recommended — query one match at a time)
        league: League ID (requires season)
        season: Season year (requires league)
        date: Date (YYYY-MM-DD)
        timezone: Timezone
        page: Page number (results are paginated)
        bookmaker: Bookmaker ID (default: 8 = Bet365). Common: 1=10Bet, 2=888sport, 6=Bwin, 11=Betway. Use get_bookmakers to find others.
        bet: Bet type ID filter — pass this to get actual odds values

    Returns odds grouped by bet type, or a summary of available bet types if no bet filter is set.
    """
    err = require_at_least_one(
        ["fixture", "league", "date"],
        {"fixture": fixture, "league": league, "date": date},
    )
    if err:
        return _error_response(err)

    result = await api_request("/odds", {
        "fixture": fixture, "league": league, "season": season,
        "date": date, "timezone": timezone, "page": page,
        "bookmaker": bookmaker, "bet": bet,
    })

    if bet is not None:
        return _simplify_odds(result)

    # No bet filter — return compact summary of available bet types
    return _summarize_available_bets(result)


@mcp.tool()
async def get_live_odds(
    fixture: int | None = None,
    league: int | None = None,
    bet: int | None = None,
) -> dict:
    """Get live/in-play betting odds.

    IMPORTANT: Use 'bet' to filter by bet type to keep response size manageable.
    Note: live odds API does not support bookmaker filtering. All returned
    bookmakers are preserved so the caller can compare prices.

    Common bet type IDs:
        1 = Match Winner, 5 = Goals Over/Under, 8 = Both Teams Score

    Args:
        fixture: Fixture ID
        league: League ID
        bet: Bet type ID filter (strongly recommended)

    Returns live odds from all bookmakers returned by API-Football.
    """
    result = await api_request("/odds/live", {
        "fixture": fixture, "league": league, "bet": bet,
    })
    return _simplify_live_odds(result)


@mcp.tool()
async def get_odds_mapping(page: int | None = None) -> dict:
    """Get mapping of fixtures available in the odds endpoint.

    Args:
        page: Page number (results are paginated)

    Returns list of fixture IDs that have odds data available.
    """
    return await api_request("/odds/mapping", {"page": page})


@mcp.tool()
async def get_bookmakers(
    id: int | None = None,
    search: str | None = None,
) -> dict:
    """Get available bookmakers and their IDs.

    Args:
        id: Bookmaker ID
        search: Search bookmaker by name (min 3 chars)

    Returns list of bookmakers with ID and name.
    Use the returned ID as the 'bookmaker' param in get_odds (default is 8 = Bet365).
    """
    return await api_request("/odds/bookmakers", {"id": id, "search": search})


@mcp.tool()
async def get_bet_types(
    id: int | None = None,
    search: str | None = None,
) -> dict:
    """Get available bet types.

    Args:
        id: Bet type ID
        search: Search bet type by name (min 3 chars)

    Returns list of bet types with ID and name.
    Use the returned ID as the 'bet' param in get_odds/get_live_odds.
    Common IDs: 1=Match Winner, 5=Goals Over/Under, 8=Both Teams Score, 12=Double Chance.
    """
    return await api_request("/odds/bets", {"id": id, "search": search})


@mcp.tool()
async def get_live_bet_types(
    id: int | None = None,
    search: str | None = None,
) -> dict:
    """Get available bet types for live/in-play odds.

    Args:
        id: Live bet type ID
        search: Search bet type by name (min 3 chars)

    Returns list of live bet types with ID and name.
    Use the returned ID as the 'bet' param in get_live_odds. These IDs differ from
    pre-match bet IDs (get_bet_types) and do not work with get_odds.
    """
    return await api_request("/odds/live/bets", {"id": id, "search": search})
