"""Tests for endpoints and parameters added in API-Football 3.9.2 / 3.9.3."""

from datetime import date

import pytest
from tests.conftest import mock_httpx_response

import sys
sys.argv = ["test"]
from server import mcp, register_tools
register_tools()

from api_client import current_season
from tools.fixtures import get_fixtures, get_rounds, get_head_to_head, get_fixture_statistics
from tools.injuries import get_injuries
from tools.odds import get_live_bet_types
from tools.players import get_player_profiles, get_player_teams
from tools.reference import get_api_status, get_leagues
from tools.search import search_player
from tools.sidelined import get_sidelined
from tools.trophies import get_trophies


def sent(mock_api):
    """Return (endpoint, params) of the last API call."""
    args, kwargs = mock_api.call_args
    return args[0], kwargs["params"]


# --- New parameters on existing tools ---

@pytest.mark.asyncio
async def test_fixtures_venue(mock_api):
    mock_api.return_value = mock_httpx_response(data=[])
    await get_fixtures(team=42, season=2026, venue=494)
    assert sent(mock_api) == ("/fixtures", {"team": 42, "season": 2026, "venue": 494})


@pytest.mark.asyncio
async def test_head_to_head_venue(mock_api):
    mock_api.return_value = mock_httpx_response(data=[])
    await get_head_to_head("33-34", venue=556)
    assert sent(mock_api) == ("/fixtures/headtohead", {"h2h": "33-34", "venue": 556})


@pytest.mark.asyncio
async def test_rounds_dates_and_timezone(mock_api):
    mock_api.return_value = mock_httpx_response(data=[
        {"round": "Regular Season - 1", "dates": ["2026-08-21", "2026-08-22"]},
    ])
    result = await get_rounds(39, 2026, dates="true", timezone="Europe/London")
    assert result["data"][0]["dates"] == ["2026-08-21", "2026-08-22"]
    assert sent(mock_api) == ("/fixtures/rounds", {
        "league": 39, "season": 2026, "dates": "true", "timezone": "Europe/London",
    })


@pytest.mark.asyncio
async def test_fixture_statistics_half(mock_api):
    mock_api.return_value = mock_httpx_response(data=[
        {"team": {"id": 42}, "statistics": [], "statistics_1h": [], "statistics_2h": []},
    ])
    result = await get_fixture_statistics(1557455, half="true")
    assert "statistics_1h" in result["data"][0]
    assert sent(mock_api) == ("/fixtures/statistics", {"fixture": 1557455, "half": "true"})


@pytest.mark.asyncio
async def test_injuries_ids(mock_api):
    mock_api.return_value = mock_httpx_response(data=[])
    await get_injuries(ids="1557455-1557453")
    assert sent(mock_api) == ("/injuries", {"ids": "1557455-1557453"})


@pytest.mark.asyncio
async def test_leagues_team(mock_api):
    mock_api.return_value = mock_httpx_response(data=[])
    await get_leagues(team=42, current="true")
    assert sent(mock_api) == ("/leagues", {"team": 42, "current": "true"})


@pytest.mark.asyncio
@pytest.mark.parametrize("tool,endpoint", [(get_sidelined, "/sidelined"), (get_trophies, "/trophies")])
async def test_multi_person_ids_map_to_api_names(mock_api, tool, endpoint):
    mock_api.return_value = mock_httpx_response(data=[])
    await tool(players="276-1460")
    assert sent(mock_api) == (endpoint, {"players": "276-1460"})
    await tool(coaches="2-6")
    assert sent(mock_api) == (endpoint, {"coachs": "2-6"})


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", [get_sidelined, get_trophies])
async def test_multi_person_tools_still_require_a_param(tool):
    result = await tool()
    assert result["success"] is False
    assert "At least one" in result["error"]


# --- New endpoints ---

@pytest.mark.asyncio
async def test_api_status(mock_api):
    mock_api.return_value = mock_httpx_response(data={
        "account": {"firstname": "A", "lastname": "B", "email": "a@example.com"},
        "subscription": {"plan": "Mega", "active": True},
        "requests": {"current": 10, "limit_day": 150000},
    })
    result = await get_api_status()
    assert result["data"]["subscription"]["plan"] == "Mega"
    assert "account" not in result["data"]
    assert sent(mock_api) == ("/status", {})


@pytest.mark.asyncio
async def test_player_profiles_search(mock_api):
    mock_api.return_value = mock_httpx_response(data=[{"player": {"id": 1460, "name": "B. Saka"}}])
    result = await get_player_profiles(search="Saka")
    assert result["data"][0]["player"]["id"] == 1460
    assert sent(mock_api) == ("/players/profiles", {"search": "Saka"})


@pytest.mark.asyncio
async def test_player_profiles_short_search_rejected(mock_api):
    result = await get_player_profiles(search="Sak")
    assert result["success"] is False
    assert "4 characters" in result["error"]
    mock_api.assert_not_called()


@pytest.mark.asyncio
async def test_player_teams(mock_api):
    mock_api.return_value = mock_httpx_response(data=[
        {"team": {"id": 42, "name": "Arsenal"}, "seasons": [2026, 2025]},
    ])
    result = await get_player_teams(1460)
    assert result["data"][0]["seasons"] == [2026, 2025]
    assert sent(mock_api) == ("/players/teams", {"player": 1460})


@pytest.mark.asyncio
async def test_live_bet_types(mock_api):
    mock_api.return_value = mock_httpx_response(data=[{"id": 1, "name": "Over/Under Extra Time"}])
    await get_live_bet_types(search="Over")
    assert sent(mock_api) == ("/odds/live/bets", {"search": "Over"})


# --- search_player uses profiles when no league/team is given ---

@pytest.mark.asyncio
async def test_search_player_without_league_uses_profiles(mock_api):
    mock_api.return_value = mock_httpx_response(data=[{
        "player": {"id": 1100, "name": "E. Haaland", "firstname": "Erling", "lastname": "Haaland",
                   "age": 26, "nationality": "Norway", "position": "Attacker", "photo": "p.png"},
    }])
    result = await search_player("Haaland")
    assert sent(mock_api) == ("/players/profiles", {"search": "Haaland"})
    assert result["success"] is True
    assert result["data"][0]["id"] == 1100
    assert result["data"][0]["position"] == "Attacker"


@pytest.mark.asyncio
async def test_search_player_with_league_defaults_to_current_season(mock_api):
    mock_api.return_value = mock_httpx_response(data=[])
    await search_player("Haaland", league=39)
    assert sent(mock_api) == ("/players", {"search": "Haaland", "league": 39, "season": current_season()})


@pytest.mark.asyncio
async def test_search_player_short_name_rejected(mock_api):
    result = await search_player("Haa")
    assert result["success"] is False
    mock_api.assert_not_called()


@pytest.mark.parametrize("today,expected", [
    (date(2026, 11, 3), 2026),
    (date(2026, 7, 1), 2026),
    (date(2027, 6, 30), 2026),
    (date(2027, 1, 15), 2026),
])
def test_current_season(today, expected):
    assert current_season(today) == expected
