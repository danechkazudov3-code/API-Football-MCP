"""Automatic pre-match candidate selection using model probabilities and best prices."""

from __future__ import annotations

from typing import Any

from api_client import api_request
from server import mcp
from tools.analyzer import analyze_match
from tools.prediction import evaluate_candidate, select_primary_candidate


_MARKET_OUTCOMES = {
    "1x2": {"home_win", "draw", "away_win"},
    "total_goals_2_5": {"over_2_5", "under_2_5"},
    "btts": {"btts_yes", "btts_no"},
}


def _market_key(bet_name: str, value: str) -> str | None:
    name = (bet_name or "").strip().lower()
    selection = (value or "").strip().lower()

    if "match winner" in name or name in {"1x2", "match result"}:
        return {"home": "home_win", "draw": "draw", "away": "away_win"}.get(selection)
    if "over/under" in name or "goals over" in name or "total goals" in name:
        if selection in {"over 2.5", "over 2,5"}:
            return "over_2_5"
        if selection in {"under 2.5", "under 2,5"}:
            return "under_2_5"
    if "both teams score" in name or "both teams to score" in name or name == "btts":
        return {"yes": "btts_yes", "no": "btts_no"}.get(selection)
    return None


def _market_group(selection_key: str) -> str | None:
    for group, outcomes in _MARKET_OUTCOMES.items():
        if selection_key in outcomes:
            return group
    return None


def extract_best_prices(
    odds_response: dict[str, Any],
    *,
    allowed_bookmakers: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Extract prices and no-vig probabilities from complete single-book markets.

    When an allowlist is supplied, only exact normalized bookmaker-name matches
    are eligible. No-vig probabilities are never synthesized across books.
    """
    best: dict[str, dict[str, Any]] = {}
    if not odds_response.get("success"):
        return best

    observed_at = odds_response.get("retrieved_at")
    for fixture in odds_response.get("data") or []:
        provider_updated_at = fixture.get("update")
        for bookmaker in fixture.get("bookmakers") or []:
            book_name = bookmaker.get("name", "Unknown")
            normalize = lambda value: "".join(ch for ch in str(value).casefold() if ch.isalnum())
            allowed_names = {normalize(name) for name in (allowed_bookmakers or set())}
            if allowed_bookmakers is not None and not any(
                normalize(book_name) == name or normalize(book_name).startswith(name)
                for name in allowed_names
            ):
                continue
            markets: dict[str, dict[str, float]] = {}

            for bet in bookmaker.get("bets") or []:
                bet_name = bet.get("name", "")
                for value in bet.get("values") or []:
                    key = _market_key(bet_name, str(value.get("value", "")))
                    if not key:
                        continue
                    try:
                        price = float(value.get("odd"))
                    except (TypeError, ValueError):
                        continue
                    if price <= 1.0:
                        continue
                    group = _market_group(key)
                    if group:
                        markets.setdefault(group, {})[key] = price

            for group, selections in markets.items():
                required = _MARKET_OUTCOMES[group]
                complete = required.issubset(selections)
                implied = {key: 1.0 / selections[key] for key in required if key in selections}
                overround = sum(implied.values()) if complete else None
                if complete and (overround is None or overround <= 0):
                    complete = False
                    overround = None

                for key, price in selections.items():
                    quote = {
                        "odds": price,
                        "bookmaker": book_name,
                        "implied_probability": round(1.0 / price, 6),
                        "no_vig_probability": (
                            round(implied[key] / overround, 6)
                            if complete and overround is not None else None
                        ),
                        "overround": round(overround - 1.0, 6) if complete and overround is not None else None,
                        "market_complete": complete,
                        "provider_updated_at": provider_updated_at,
                        "odds_observed_at": observed_at,
                        "odds_source": "API-Football",
                    }
                    if key not in best or price > best[key]["odds"]:
                        best[key] = quote
    return best


@mcp.tool()
async def predict_match_bet(fixture_id: int) -> dict[str, Any]:
    """Generate a primary pre-match pick and keep all supported candidates visible."""
    analysis = await analyze_match(fixture_id)
    if not analysis.get("success"):
        return {
            "success": False,
            "stage": "match_analysis",
            "error": analysis.get("error", "Match analysis failed."),
        }

    forecast = analysis.get("forecast") or {}
    if not forecast.get("available"):
        return {
            "success": True,
            "status": "INSUFFICIENT_DATA",
            "fixture": analysis.get("fixture"),
            "analysis_status": analysis.get("analysis_status"),
            "match_analysis": {
                "recent_form": analysis.get("recent_form"),
                "head_to_head": analysis.get("head_to_head"),
                "injuries": analysis.get("injuries"),
                "season_statistics": analysis.get("season_statistics"),
                "data_limitations": analysis.get("data_limitations"),
            },
            "primary_pick": None,
            "candidates": [],
            "reason": forecast.get("reason", "Not enough recent-form data."),
        }

    prices_response = await api_request("/odds", {"fixture": fixture_id})
    # MyAnalytics current execution policy: use PARI prices only; never silently substitute another book.
    best_prices = extract_best_prices(prices_response, allowed_bookmakers={"PARI"})
    candidates = []

    for item in forecast.get("candidates") or []:
        candidate = dict(item)
        market_key = next(
            (key for key, label in {
                "home_win": "Home win", "draw": "Draw", "away_win": "Away win",
                "over_2_5": "Over 2.5", "under_2_5": "Under 2.5",
                "btts_yes": "Yes", "btts_no": "No",
            }.items() if label == candidate.get("selection") and (
                (key in {"home_win", "draw", "away_win"} and candidate.get("market") == "1X2")
                or (key in {"over_2_5", "under_2_5"} and candidate.get("market") == "Total goals 2.5")
                or (key in {"btts_yes", "btts_no"} and candidate.get("market") == "Both teams to score")
            )),
            None,
        )
        price = best_prices.get(market_key) if market_key else None
        if price:
            candidate.update(price)
        candidate = evaluate_candidate(candidate, model_validated=False)
        candidates.append(candidate)

    primary = select_primary_candidate(candidates)
    most_likely = max(
        (item for item in candidates if 0.0 < float(item.get("model_probability") or 0.0) < 1.0),
        key=lambda item: float(item["model_probability"]),
        default=None,
    )
    return {
        "success": True,
        "status": primary.get("status") if primary else "INSUFFICIENT_DATA",
        "fixture": analysis.get("fixture"),
        "analysis_status": analysis.get("analysis_status"),
        "match_analysis": {
            "recent_form": analysis.get("recent_form"),
            "head_to_head": analysis.get("head_to_head"),
            "injuries": analysis.get("injuries"),
            "season_statistics": analysis.get("season_statistics"),
            "data_limitations": analysis.get("data_limitations"),
        },
        "model": forecast.get("model"),
        "model_validated": False,
        "primary_pick": primary,
        "most_likely_outcome": most_likely,
        "candidates": candidates,
        "odds_source": "API-Football; PARI only; no bookmaker substitution",
        "odds_available": bool(best_prices),
        "odds_retrieved_at": prices_response.get("retrieved_at"),
        "odds_error": prices_response.get("error") if not prices_response.get("success") else None,
        "warning": (
            "Experimental Poisson baseline only; it has not been calibrated or backtested. "
            "Positive EV plus positive PARI no-vig edge may be labelled LEAN; VALUE_BET remains disabled until validation."
        ),
        "rate_limit_remaining": prices_response.get("rate_limit_remaining"),
    }
