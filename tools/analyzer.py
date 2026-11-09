"""Aggregated match analysis tool."""

from __future__ import annotations

from typing import Any

from api_client import api_request, _error_response
from server import mcp

@mcp.tool()
async def analyze_match(fixture_id: int) -> dict[str, Any]:
    """Collect match data using one API request."""

    if not fixture_id or fixture_id <= 0:
        return _error_response("A valid fixture_id is required.")

    result = await api_request(
        "/fixtures",
        {"ids": str(fixture_id)},
    )

    if not result.get("success"):
        return {
            "success": False,
            "stage": "data_collection",
            "error": result.get("error", "Could not load match data."),
        }

    matches = result.get("data", [])

    if not matches:
        return _error_response("Fixture not found.")

    match = matches[0]

    return {
        "success": True,
        "analysis_status": "DATA_COLLECTION_ONLY",
        "message": "Match data collected. Probability and betting value calculations are not yet implemented.",
        "fixture": {
            "id": fixture_id,
            "date": match.get("fixture", {}).get("date"),
            "status": match.get("fixture", {}).get("status"),
            "venue": match.get("fixture", {}).get("venue"),
            "league": match.get("league"),
            "teams": match.get("teams"),
            "goals": match.get("goals"),
            "score": match.get("score"),
        },
        "raw_data": match,
        "rate_limit_remaining": result.get("rate_limit_remaining"),
    }





