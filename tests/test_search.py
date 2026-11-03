"""Tests for search/name-resolution tools."""

import pytest

from tests.conftest import mock_httpx_response


# Need to register tools first
import sys
sys.argv = ["test"]
from server import mcp, register_tools
register_tools()

from tools.search import search_team, search_player, search_league, search_coach, search_venue


@pytest.mark.asyncio
async def test_search_team_success(mock_api):
    mock_api.return_value = mock_httpx_response(data=[
        {
            "team": {"id": 33, "name": "Manchester United", "code": "MUN", "country": "England", "founded": 1878, "logo": "logo.png"},
            "venue": {"name": "Old Trafford", "city": "Manchester", "capacity": 76212},
        },
        {
            "team": {"id": 50, "name": "Manchester City", "code": "MCI", "country": "England", "founded": 1880, "logo": "logo2.png"},
            "venue": {"name": "Etihad Stadium", "city": "Manchester", "capacity": 55017},
        },
    ])
    result = await search_team("Manchester")
    assert result["success"] is True
    assert result["results"] == 2
    assert result["data"][0]["id"] == 33
    assert result["data"][0]["name"] == "Manchester United"
    assert result["data"][1]["id"] == 50


@pytest.mark.asyncio
async def test_search_team_short_name():
    result = await search_team("AB")
    assert result["success"] is False
    assert "3 characters" in result["error"]


@pytest.mark.asyncio
async def test_search_player_success(mock_api):
    mock_api.return_value = mock_httpx_response(data=[
        {
            "player": {"id": 1100, "name": "E. Haaland", "firstname": "Erling", "lastname": "Haaland", "age": 24, "nationality": "Norway", "photo": "photo.png"},
            "statistics": [{"team": {"id": 50, "name": "Manchester City"}}],
        }
    ])
    result = await search_player("Haaland", league=39, season=2024)
    assert result["success"] is True
    assert result["data"][0]["id"] == 1100
    assert result["data"][0]["team_name"] == "Manchester City"


@pytest.mark.asyncio
async def test_search_player_without_league_searches_profiles(mock_api):
    mock_api.return_value = mock_httpx_response(data=[
        {"player": {"id": 1100, "name": "E. Haaland"}},
    ])
    result = await search_player("Haaland")
    assert result["success"] is True
    assert mock_api.call_args[0][0] == "/players/profiles"


@pytest.mark.asyncio
async def test_search_league_success(mock_api):
    mock_api.return_value = mock_httpx_response(data=[
        {
            "league": {"id": 39, "name": "Premier League", "type": "League", "logo": "logo.png"},
            "country": {"name": "England", "code": "GB"},
            "seasons": [{"year": 2022}, {"year": 2023}, {"year": 2024}],
        }
    ])
    result = await search_league("Premier")
    assert result["success"] is True
    assert result["data"][0]["id"] == 39
    assert result["data"][0]["country"] == "England"


@pytest.mark.asyncio
async def test_search_coach_success(mock_api):
    mock_api.return_value = mock_httpx_response(data=[
        {
            "id": 4, "name": "P. Guardiola", "firstname": "Pep", "lastname": "Guardiola",
            "age": 53, "nationality": "Spain", "photo": "photo.png",
            "career": [
                {"team": {"name": "Manchester City"}, "start": "2016-07-01", "end": None},
                {"team": {"name": "Bayern Munich"}, "start": "2013-07-01", "end": "2016-06-30"},
            ],
        }
    ])
    result = await search_coach("Guardiola")
    assert result["success"] is True
    assert result["data"][0]["id"] == 4
    assert result["data"][0]["current_team"] == "Manchester City"


@pytest.mark.asyncio
async def test_search_venue_success(mock_api):
    mock_api.return_value = mock_httpx_response(data=[
        {"id": 556, "name": "Old Trafford", "city": "Manchester", "country": "England", "capacity": 76212, "surface": "grass", "address": "Sir Matt Busby Way"},
    ])
    result = await search_venue("Old Trafford")
    assert result["success"] is True
    assert result["data"][0]["id"] == 556
    assert result["data"][0]["capacity"] == 76212
