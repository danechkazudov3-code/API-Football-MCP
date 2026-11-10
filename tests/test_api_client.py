"""Tests for the API client: error handling, rate limits, param stripping."""

import os
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from api_client import api_request, require_params, require_at_least_one, _error_response
from tests.conftest import mock_httpx_response


@pytest.mark.asyncio
async def test_successful_request(mock_api):
    mock_api.return_value = mock_httpx_response(data=[{"id": 1, "name": "Test"}])
    result = await api_request("/test", {"key": "value"})
    assert result["success"] is True
    assert result["results"] == 1
    assert result["data"] == [{"id": 1, "name": "Test"}]
    assert result["rate_limit_remaining"] == 149990
    assert result["retrieved_at"]


@pytest.mark.asyncio
async def test_none_params_stripped(mock_api):
    mock_api.return_value = mock_httpx_response(data=[])
    await api_request("/test", {"keep": "value", "drop": None, "also_drop": None})
    call_args = mock_api.call_args
    assert call_args[1]["params"] == {"keep": "value"}


@pytest.mark.asyncio
async def test_api_errors_returned(mock_api):
    mock_api.return_value = mock_httpx_response(
        errors={"league": "The League field is required.", "team": "The Team field is required."}
    )
    result = await api_request("/players", {"search": "test"})
    assert result["success"] is False
    assert "league" in result["error"].lower() or "League" in result["error"]
    assert "error_details" in result


@pytest.mark.asyncio
async def test_http_401(mock_api):
    mock_api.return_value = httpx.Response(
        status_code=401,
        json={"errors": {}},
        request=httpx.Request("GET", "https://v3.football.api-sports.io/test"),
    )
    result = await api_request("/test")
    assert result["success"] is False
    assert "API key" in result["error"]


@pytest.mark.asyncio
async def test_http_429(mock_api):
    mock_api.return_value = httpx.Response(
        status_code=429,
        json={"errors": {}},
        request=httpx.Request("GET", "https://v3.football.api-sports.io/test"),
    )
    result = await api_request("/test")
    assert result["success"] is False
    assert "лимит запросов API-Football исчерпан" in result["error"]


@pytest.mark.asyncio
async def test_http_500(mock_api):
    mock_api.return_value = httpx.Response(
        status_code=500,
        json={"errors": {}},
        request=httpx.Request("GET", "https://v3.football.api-sports.io/test"),
    )
    result = await api_request("/test")
    assert result["success"] is False
    assert "server error" in result["error"].lower()


@pytest.mark.asyncio
async def test_timeout(mock_api):
    mock_api.side_effect = httpx.TimeoutException("timed out")
    result = await api_request("/test")
    assert result["success"] is False
    assert "timed out" in result["error"].lower()


@pytest.mark.asyncio
async def test_connection_error(mock_api):
    mock_api.side_effect = httpx.ConnectError("connection refused")
    result = await api_request("/test")
    assert result["success"] is False
    assert "connect" in result["error"].lower()


@pytest.mark.asyncio
async def test_missing_api_key():
    import api_client
    original_key = api_client.API_KEY
    api_client.API_KEY = ""
    try:
        result = await api_request("/test")
        assert result["success"] is False
        assert "API key" in result["error"]
    finally:
        api_client.API_KEY = original_key


@pytest.mark.asyncio
async def test_rate_limit_header_parsed(mock_api):
    mock_api.return_value = mock_httpx_response(
        data=[],
        headers={"x-ratelimit-requests-remaining": "42"},
    )
    result = await api_request("/test")
    assert result["rate_limit_remaining"] == 42


def test_require_params_all_present():
    assert require_params(["a", "b"], {"a": 1, "b": 2}) is None


def test_require_params_missing():
    result = require_params(["a", "b"], {"a": 1})
    assert result is not None
    assert "b" in result


def test_require_at_least_one_satisfied():
    assert require_at_least_one(["a", "b"], {"a": 1}) is None


def test_require_at_least_one_none():
    result = require_at_least_one(["a", "b"], {"a": None, "b": None})
    assert result is not None


def test_error_response():
    result = _error_response("Something went wrong", {"field": "error"})
    assert result["success"] is False
    assert result["error"] == "Something went wrong"
    assert result["error_details"] == {"field": "error"}


@pytest.mark.asyncio
async def test_cache_reuses_successful_historical_fixture_request(mock_api):
    import api_client

    mock_api.return_value = mock_httpx_response(data=[{"fixture": {"id": 1}}])
    params = {"team": 50, "last": 5}
    first = await api_request("/fixtures", params)
    second = await api_request("/fixtures", params)

    assert first["success"] is True
    assert second["data"] == first["data"]
    assert second["retrieved_at"] == first["retrieved_at"]
    assert mock_api.call_count == 1
    assert len(api_client._response_cache) == 1


@pytest.mark.asyncio
async def test_live_odds_requests_bypass_cache(mock_api):
    mock_api.return_value = mock_httpx_response(data=[{"fixture": {"id": 1}}])

    await api_request("/odds/live", {"fixture": 123})
    await api_request("/odds/live", {"fixture": 123})

    assert mock_api.call_count == 2
