"""Aggregated match analysis tool."""

from __future__ import annotations

import asyncio
from typing import Any

from api_client import api_request, _error_response
from server import mcp

@mcp.tool()
async def analyze_match(
    fixture_id: int,
) -> dict[str, Any]:
    """Collect a compact data package for one football match.

    Fetches fixture details, statistics, events, lineups, player stats,
    and head-to-head history. All collection is performed server-side.
    """

    if not fixture_id or fixture_id <= 0:
        return _error_response("A valid fixture_id is required.")

    # The fixture endpoint with id returns the match details.
    # The ids parameter can return several match data sections in one call.
    fixture_task = api_request(
        "/fixtures",
        {"id": fixture_id},
    )

    details_task = api_request(
        "/fixtures",
        {"ids": str(fixture_id)},
    )

    fixture, details = await asyncio.gather(
        fixture_task,
        details_task,
    )

    if not fixture.get("success"):
        return {
            "success": False,
            "stage": "fixture",
            "error": fixture.get("error", "Could not load fixture."),
        }

    if not fixture.get("data"):
        return _error_response("Fixture not found.")

    match = fixture["data"][0]

    home = match.get("teams", {}).get("home", {})
    away = match.get("teams", {}).get("away", {})

    return {
        "success": True,
        "analysis_status": "DATA_COLLECTION_ONLY",
        "message": (
            "Match data collected. This tool does not yet calculate "
            "probabilities or betting value."
        ),
        "fixture": {
            "id": fixture_id,
            "date": match.get("fixture", {}).get("date"),
            "status": match.get("fixture", {}).get("status", {}),
            "venue": match.get("fixture", {}).get("venue", {}),
            "league": match.get("league", {}),
            "home": home,
            "away": away,
            "score": match.get("score", {}),
        },
        "match_data": details.get("data", []),
        "data_collection_success": details.get("success", False),
        "data_collection_error": details.get("error"),
        "rate_limit_remaining": details.get("rate_limit_remaining"),
    }





