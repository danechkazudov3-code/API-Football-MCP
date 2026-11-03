"""Shared API client for API-Football v3 with error handling and rate-limit tracking."""

import json
import os
from datetime import date
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://v3.football.api-sports.io"
API_KEY = os.getenv("API_FOOTBALL_KEY", "")
TIMEOUT = 30.0

_client: httpx.AsyncClient | None = None
_rate_limit_remaining: int | None = None


async def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={"x-apisports-key": API_KEY},
            timeout=TIMEOUT,
        )
    return _client


async def api_request(endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Make a request to the API-Football v3 API.

    Args:
        endpoint: API endpoint path (e.g., "/players", "/fixtures/statistics")
        params: Query parameters. None values are stripped automatically.

    Returns:
        Structured response dict with keys: success, results, data, paging, rate_limit_remaining.
        On error: success=False with error and error_details keys.
    """
    global _rate_limit_remaining

    if not API_KEY:
        return _error_response("API key not configured. Set API_FOOTBALL_KEY in .env file.")

    # Strip None values from params
    clean_params = {}
    if params:
        for k, v in params.items():
            if v is not None:
                clean_params[k] = v

    try:
        client = await get_client()
        response = await client.get(endpoint, params=clean_params)
    except httpx.TimeoutException:
        return _error_response(f"Request to {endpoint} timed out after {TIMEOUT}s. Try again or use more specific filters.")
    except httpx.ConnectError:
        return _error_response("Could not connect to API-Football. Check your internet connection.")
    except httpx.HTTPError as e:
        return _error_response(f"HTTP error: {e}")

    # Track rate limits from headers
    remaining = response.headers.get("x-ratelimit-requests-remaining")
    if remaining is not None:
        try:
            _rate_limit_remaining = int(remaining)
        except ValueError:
            pass

    # Handle HTTP-level errors
    if response.status_code == 401:
        return _error_response("Invalid API key. Check your API_FOOTBALL_KEY in .env file.")
    if response.status_code == 429:
        return _error_response("Rate limit exceeded. You've hit the daily request limit (150,000/day).")
    if response.status_code >= 500:
        return _error_response(f"API-Football server error (HTTP {response.status_code}). Try again later.")
    if response.status_code >= 400:
        return _error_response(f"Bad request (HTTP {response.status_code}). Check your parameters.")

    # Parse JSON response
    try:
        data = response.json()
    except (json.JSONDecodeError, ValueError):
        return _error_response("Invalid JSON response from API-Football.")

    # Check for API-level errors
    errors = data.get("errors", {})
    if errors:
        if isinstance(errors, dict) and errors:
            details = {k: v for k, v in errors.items()}
            msg = "; ".join(f"{k}: {v}" for k, v in details.items())
            return _error_response(f"API error — {msg}", error_details=details)
        if isinstance(errors, list) and errors:
            return _error_response(f"API error — {'; '.join(str(e) for e in errors)}")

    return {
        "success": True,
        "results": data.get("results", 0),
        "data": data.get("response", []),
        "paging": data.get("paging", {}),
        "rate_limit_remaining": _rate_limit_remaining,
    }


def _error_response(message: str, error_details: dict | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "success": False,
        "results": 0,
        "data": [],
        "error": message,
        "rate_limit_remaining": _rate_limit_remaining,
    }
    if error_details:
        result["error_details"] = error_details
    return result


def current_season(today: date | None = None) -> int:
    """Return the current European-style season year (2026 for 2026/27).

    Seasons are named by their starting year and start around July, so
    January–June belongs to the previous year's season.
    """
    today = today or date.today()
    return today.year if today.month >= 7 else today.year - 1


def require_params(names: list[str], values: dict[str, Any]) -> str | None:
    """Validate that all required parameters are provided (not None).

    Returns an error message string if validation fails, or None if all params are present.
    """
    missing = [n for n in names if values.get(n) is None]
    if missing:
        return f"Missing required parameter(s): {', '.join(missing)}"
    return None


def require_at_least_one(names: list[str], values: dict[str, Any]) -> str | None:
    """Validate that at least one of the named parameters is provided.

    Returns an error message string if validation fails, or None if at least one is present.
    """
    if not any(values.get(n) is not None for n in names):
        return f"At least one of these parameters is required: {', '.join(names)}"
    return None
