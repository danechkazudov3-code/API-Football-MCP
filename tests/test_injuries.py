"""Tests for injuries tool."""

import pytest
from tests.conftest import mock_httpx_response

import sys
sys.argv = ["test"]
from server import mcp, register_tools
register_tools()

from tools.injuries import get_injuries


@pytest.mark.asyncio
async def test_get_injuries_by_fixture(mock_api):
    mock_api.return_value = mock_httpx_response(data=[
        {"player": {"id": 1, "name": "Test Player"}, "team": {"id": 33}, "fixture": {"id": 1035050}, "league": {"id": 39}},
    ])
    result = await get_injuries(fixture=1035050)
    assert result["success"] is True


@pytest.mark.asyncio
async def test_get_injuries_by_league_season(mock_api):
    mock_api.return_value = mock_httpx_response(data=[], results=0)
    result = await get_injuries(league=39, season=2024)
    assert result["success"] is True


@pytest.mark.asyncio
async def test_get_injuries_requires_at_least_one_filter(mock_api):
    result = await get_injuries()
    assert result["success"] is False
    assert "At least one" in result["error"]
    mock_api.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_injuries_requires_season_for_league_team_and_player(mock_api):
    for kwargs in ({"league": 39}, {"team": 33}, {"player": 276}):
        result = await get_injuries(**kwargs)
        assert result["success"] is False
        assert "season parameter is required" in result["error"]
    mock_api.assert_not_awaited()
