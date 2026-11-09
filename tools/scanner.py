"""Automatic discovery and ranking of upcoming football betting opportunities."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from api_client import api_request
from server import mcp
from tools.recommendation import predict_match_bet
from tools.open_matchday_provider import fetch_open_matchday_scan
from tools.poisson_model import forecast_from_recent_form
from tools.prediction_journal import record_scan_reports


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



def _format_fallback_result(
    fallback: dict[str, Any], start: date, end: date, timezone_name: str,
    api_error: str | None,
) -> dict[str, Any]:
    fallback_reports = []
    for entry in fallback.get("fixtures") or []:
        forecast = forecast_from_recent_form(
            entry["model_home_form"], entry["model_away_form"]
        )
        forecast = dict(forecast)
        no_odds_reason = "No bookmaker odds are supplied by the fallback source; fair odds are model estimates only."
        if forecast.get("available"):
            if forecast.get("primary_forecast"):
                forecast["primary_forecast"] = {
                    **forecast["primary_forecast"], "status": "INSUFFICIENT_DATA",
                    "odds": None, "reason": no_odds_reason,
                }
            forecast["candidates"] = [
                {**candidate, "status": "INSUFFICIENT_DATA", "odds": None,
                 "reason": no_odds_reason}
                for candidate in (forecast.get("candidates") or [])
            ]
        fallback_reports.append({
            "fixture": entry["fixture"],
            "success": bool(forecast.get("available")),
            "status": "INSUFFICIENT_DATA" if not forecast.get("available") else "NO_BET",
            "primary_pick": None,
            "forecast_candidates": [
                {
                    **candidate, "status": "INSUFFICIENT_DATA", "odds": None,
                    "reason": no_odds_reason,
                }
                for candidate in (forecast.get("candidates") or [])
            ],
            "forecast": forecast,
            "match_analysis": {
                "recent_form": {"home": entry["home_form"], "away": entry["away_form"]},
                "venue_form": {"home": entry["home_venue_form"], "away": entry["away_venue_form"]},
                "match_statistics": {
                    "home": (entry.get("model_home_form") or {}).get("statistics"),
                    "away": (entry.get("model_away_form") or {}).get("statistics"),
                    "note": "Partial historical match statistics; no xG is supplied by Open-Matchday.",
                },
                "head_to_head": {"available": False, "reason": "Not supplied by fallback dataset."},
                "injuries": {"available": False, "reason": "Not supplied by fallback dataset."},
                "lineups": {"available": False, "reason": "Not supplied by fallback dataset."},
            },
            "odds_available": False,
            "reason": forecast.get("reason") or "Probability forecast only; no bookmaker prices available.",
        })
    journal = record_scan_reports(
        fallback_reports, data_source=fallback.get("source") or "open-matchday"
    )
    return {
        "success": True,
        "journal": journal,
        "status": "FALLBACK_SCAN_COMPLETED" if fallback_reports else "NO_UPCOMING_FIXTURES",
        "data_source": fallback.get("source"),
        "scan_window": {"from": start.isoformat(), "to": end.isoformat()},
        "timezone": timezone_name,
        "fixtures_found": fallback.get("fixtures_found_in_window", 0),
        "fixtures_selected": len(fallback_reports),
        "fixtures_analyzed": len(fallback_reports),
        "ranked_opportunities": [],
        "all_matches": fallback_reports,
        "best_opportunity": None,
        "model_validated": False,
        "api_football_error": api_error,
        "data_limitations": fallback.get("data_limitations", []),
        "warning": "Fallback produces experimental probabilities only. No odds, injuries, lineups, or live data; do not treat any selection as a bet recommendation.",
    }

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
    if (
        not fixtures_result.get("success")
        or not fixtures_result.get("data")
        or not any(
            (item.get("fixture") or {}).get("status", {}).get("short") in {"NS", "TBD"}
            for item in (fixtures_result.get("data") or [])
        )
    ):
        fallback = await fetch_open_matchday_scan(
            league_id, start.isoformat(), end.isoformat(), max_fixtures
        )
        if not fallback.get("success"):
            return {
                "success": False, "stage": "fixture_discovery",
                "error": fixtures_result.get("error", "No API-Football fixtures."),
                "api_football_error": fixtures_result.get("error", "No API-Football fixtures."),
                "fallback_error": fallback.get("error"),
                "fallback_source": fallback.get("source", "open-matchday"),
                "rate_limit_remaining": fixtures_result.get("rate_limit_remaining"),
            }
        return _format_fallback_result(
            fallback, start, end, timezone_name,
            fixtures_result.get("error", "API-Football returned no fixtures."),
        )
    remaining_quota = fixtures_result.get("rate_limit_remaining")
    if not fixtures_result.get("success"):
        return {
            "success": False, "stage": "fixture_discovery",
            "error": fixtures_result.get("error", "Could not retrieve fixtures."),
            "rate_limit_remaining": remaining_quota,
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
            "match_analysis": result.get("match_analysis"),
            "reason": result.get("reason") or result.get("error"),
            "odds_available": result.get("odds_available", False),
        })
        remaining = result.get("rate_limit_remaining")
        if isinstance(remaining, int):
            remaining_quota = remaining
        if isinstance(remaining, int) and remaining <= 2:
            break

    if any(not entry.get("success") for entry in reports):
        fallback = await fetch_open_matchday_scan(
            league_id, start.isoformat(), end.isoformat(), max_fixtures
        )
        if fallback.get("success") and fallback.get("fixtures"):
            return _format_fallback_result(
                fallback, start, end, timezone_name,
                "API-Football fixture discovery worked, but one or more match analyses failed.",
            )

    ranked = sorted(
        (entry for entry in reports if entry.get("primary_pick")),
        key=_rank_key,
    )
    journal = record_scan_reports(reports, data_source="api-football")
    return {
        "success": True,
        "journal": journal,
        "status": "SCAN_COMPLETED" if reports else "NO_UPCOMING_FIXTURES",
        "scan_window": {"from": start.isoformat(), "to": end.isoformat()},
        "timezone": timezone_name,
        "fixtures_found": len(upcoming),
        "fixtures_selected": len(selected),
        "fixtures_analyzed": len(reports),
        "ranked_opportunities": ranked,
        "all_matches": reports,
        "best_opportunity": ranked[0] if ranked else None,
        "model_validated": False,
        "warning": (
            "Experimental model; ranking is not proof of positive long-term ROI. "
            "VALUE_BET remains disabled until out-of-sample validation."
        ),
        "rate_limit_remaining": remaining_quota,
    }
