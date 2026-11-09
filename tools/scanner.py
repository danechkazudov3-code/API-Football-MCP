"""Automatic discovery and ranking of upcoming football betting opportunities."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from api_client import api_request
from server import mcp
from tools.recommendation import predict_match_bet


def _rank_key(entry: dict[str, Any]) -> tuple[int, int, float, float]:
    pick = entry.get("primary_pick") or {}
    status = {"VALUE_BET": 0, "LEAN": 1, "WATCHLIST": 2, "NO_BET": 3,
              "INSUFFICIENT_DATA": 4}.get(pick.get("status"), 5)
    odds_profile = {"PREFERRED": 0, "LOW_ODDS": 1, "HIGH_VARIANCE": 2}.get(
        pick.get("odds_profile"), 3
    )
    try:
        ev = float(pick.get("conservative_expected_value", pick.get("expected_value")))
    except (TypeError, ValueError):
        ev = float("-inf")
    try:
        probability = float(pick.get("model_probability"))
    except (TypeError, ValueError):
        probability = float("-inf")
    return status, odds_profile, -ev, -probability


@mcp.tool()
async def scan_best_bets(
    scan_date: str | None = None,
    days_ahead: int = 1,
    league_id: int | None = None,
    max_fixtures: int = 5,
    timezone_name: str = "UTC",
) -> dict[str, Any]:
    """Find upcoming fixtures, analyze a capped number, and rank their primary picks.

    Each analyzed fixture consumes multiple API requests. The default cap is five
    and the hard cap is ten to protect the free API quota. Missing prices are never
    invented; all available candidates remain visible in each match report.
    """
    if not 1 <= days_ahead <= 7:
        return {"success": False, "error": "days_ahead must be between 1 and 7."}
    if not 1 <= max_fixtures <= 10:
        return {"success": False, "error": "max_fixtures must be between 1 and 10."}
    try:
        start = date.fromisoformat(scan_date) if scan_date else datetime.now(timezone.utc).date()
        end = start + timedelta(days=days_ahead - 1)
    except ValueError:
        return {"success": False, "error": "scan_date must use YYYY-MM-DD format."}

    params: dict[str, Any] = {
        "from": start.isoformat(), "to": end.isoformat(), "timezone": timezone_name,
    }
    if league_id is not None:
        params["league"] = league_id
    fixtures_result = await api_request("/fixtures", params)
    if not fixtures_result.get("success"):
        return {
            "success": False, "stage": "fixture_discovery",
            "error": fixtures_result.get("error", "Could not retrieve fixtures."),
            "rate_limit_remaining": fixtures_result.get("rate_limit_remaining"),
        }

    upcoming = [
        item for item in (fixtures_result.get("data") or [])
        if (item.get("fixture") or {}).get("status", {}).get("short") in {"NS", "TBD"}
    ]
    upcoming.sort(key=lambda item: (item.get("fixture") or {}).get("date") or "")
    selected = upcoming[:max_fixtures]
    reports: list[dict[str, Any]] = []

    # Sequential calls avoid a burst against the user's limited daily API quota.
    for item in selected:
        fixture = item.get("fixture") or {}
        fixture_id = fixture.get("id")
        if not fixture_id:
            continue
        result = await predict_match_bet(int(fixture_id))
        reports.append({
            "fixture": {
                "id": fixture_id, "date": fixture.get("date"),
                "league": item.get("league"), "teams": item.get("teams"),
            },
            "success": result.get("success", False),
            "status": result.get("status", "INSUFFICIENT_DATA"),
            "primary_pick": result.get("primary_pick"),
            "candidates": result.get("candidates", []),
            "reason": result.get("reason") or result.get("error"),
            "odds_available": result.get("odds_available", False),
        })
        remaining = result.get("rate_limit_remaining")
        if isinstance(remaining, int) and remaining <= 2:
            break

    ranked = sorted(
        (entry for entry in reports if entry.get("primary_pick")),
        key=_rank_key,
    )
    return {
        "success": True,
        "status": "SCAN_COMPLETED" if reports else "NO_UPCOMING_FIXTURES",
        "scan_window": {"from": start.isoformat(), "to": end.isoformat()},
        "timezone": timezone_name,
        "fixtures_found": len(upcoming),
        "fixtures_selected": len(selected),
        "fixtures_analyzed": len(reports),
        "ranked_opportunities": ranked,
        "best_opportunity": ranked[0] if ranked else None,
        "model_validated": False,
        "warning": (
            "Experimental model; ranking is not proof of positive long-term ROI. "
            "VALUE_BET remains disabled until out-of-sample validation."
        ),
        "rate_limit_remaining": fixtures_result.get("rate_limit_remaining"),
    }
