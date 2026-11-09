"""Shared test fixtures and mock helpers."""

import os
import sys
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from dotenv import load_dotenv

# Ensure project root is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Load .env first so we get the real API key for integration tests
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# Only set a dummy key if no real key is available (for unit tests in CI etc.)
if not os.environ.get("API_FOOTBALL_KEY"):
    os.environ["API_FOOTBALL_KEY"] = "test_key_12345"


def make_api_response(
    data: list | dict = None,
    results: int | None = None,
    errors: dict | list | None = None,
    paging: dict | None = None,
    get: str = "test",
) -> dict:
    """Build a mock API-Football JSON response."""
    if data is None:
        data = []
    if errors is None:
        errors = []
    if paging is None:
        paging = {"current": 1, "total": 1}
    if results is None:
        results = len(data) if isinstance(data, list) else 1
    return {
        "get": get,
        "parameters": {},
        "errors": errors,
        "results": results,
        "paging": paging,
        "response": data,
    }


def mock_httpx_response(
    data: list | dict = None,
    results: int | None = None,
    errors: dict | list | None = None,
    status_code: int = 200,
    headers: dict | None = None,
) -> httpx.Response:
    """Create a mock httpx.Response with given API-Football data."""
    body = make_api_response(data=data, results=results, errors=errors)
    if headers is None:
        headers = {"x-ratelimit-requests-remaining": "149990"}
    return httpx.Response(
        status_code=status_code,
        json=body,
        headers=headers,
        request=httpx.Request("GET", "https://v3.football.api-sports.io/test"),
    )


@pytest.fixture
def mock_api():
    """Fixture that patches httpx.AsyncClient.get to return mock responses.

    Usage in tests:
        async def test_something(mock_api):
            mock_api.return_value = mock_httpx_response(data=[...])
            result = await some_tool()
            assert result["success"] is True
    """
    with patch("api_client.get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        yield mock_client.get


@pytest.fixture(autouse=True)
def reset_api_client():
    """Reset the global client between tests."""
    import api_client
    api_client._client = None
    api_client._rate_limit_remaining = None
    api_client._response_cache.clear()
    api_client.API_KEY = os.environ.get("API_FOOTBALL_KEY", "")
    yield
