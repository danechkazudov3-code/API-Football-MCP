"""Integration tests that call the live API-Football API.

Run with: pytest tests/test_integration.py -v
These tests use real API calls and count against your daily limit.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Only run if API key is set and we're not in CI
API_KEY = os.getenv("API_FOOTBALL_KEY", "")
pytestmark = pytest.mark.skipif(not API_KEY, reason="No API key set")

# Register tools
sys.argv = ["test"]
from server import register_tools
register_tools()

from tools.search import search_team, search_player, search_league, search_coach, search_venue
from tools.reference import get_timezones, get_countries, get_seasons, get_leagues
from tools.teams import get_teams, get_team_statistics, get_team_seasons, get_team_countries
from tools.players import get_players, get_player_squads, get_player_seasons, get_top_scorers
from tools.fixtures import get_fixtures, get_rounds, get_head_to_head, get_fixture_statistics, get_fixture_events
from tools.standings import get_standings
from tools.coaches import get_coaches
from tools.venues import get_venues
from tools.transfers import get_transfers
from tools.trophies import get_trophies
from tools.sidelined import get_sidelined
from tools.injuries import get_injuries
from tools.predictions import get_predictions
from tools.odds import get_bookmakers, get_bet_types


# --- Search / Name Resolution ---

@pytest.mark.asyncio
async def test_search_team_manchester():
    result = await search_team("Manchester")
    assert result["success"] is True
    assert result["results"] > 0
    names = [t["name"] for t in result["data"]]
    assert any("Manchester" in n for n in names)


@pytest.mark.asyncio
async def test_search_player_haaland():
    result = await search_player("Haaland", league=39, season=2024)
    assert result["success"] is True
    assert result["results"] > 0
    assert any(p["name"] and "Haaland" in p["name"] for p in result["data"])


@pytest.mark.asyncio
async def test_search_league_premier():
    result = await search_league("Premier League")
    assert result["success"] is True
    assert result["results"] > 0
    assert any(l["name"] == "Premier League" for l in result["data"])


@pytest.mark.asyncio
async def test_search_coach_guardiola():
    result = await search_coach("Guardiola")
    assert result["success"] is True
    assert result["results"] > 0
    assert any("Guardiola" in c["name"] for c in result["data"])


@pytest.mark.asyncio
async def test_search_venue_old_trafford():
    result = await search_venue("Old Trafford")
    assert result["success"] is True
    assert result["results"] > 0
    assert any("Old Trafford" in v["name"] for v in result["data"])


# --- Reference Data ---

@pytest.mark.asyncio
async def test_live_timezones():
    result = await get_timezones()
    assert result["success"] is True
    assert result["results"] > 100


@pytest.mark.asyncio
async def test_live_countries():
    result = await get_countries()
    assert result["success"] is True
    assert result["results"] > 50


@pytest.mark.asyncio
async def test_live_seasons():
    result = await get_seasons()
    assert result["success"] is True
    assert 2024 in result["data"]


@pytest.mark.asyncio
async def test_live_leagues():
    result = await get_leagues(country="England", season=2024)
    assert result["success"] is True
    assert result["results"] > 0


# --- Teams ---

@pytest.mark.asyncio
async def test_live_get_teams():
    result = await get_teams(id=33)
    assert result["success"] is True
    assert result["data"][0]["team"]["name"] == "Manchester United"


@pytest.mark.asyncio
async def test_live_team_statistics():
    result = await get_team_statistics(team=33, league=39, season=2024)
    assert result["success"] is True


@pytest.mark.asyncio
async def test_live_team_seasons():
    result = await get_team_seasons(team=33)
    assert result["success"] is True
    assert len(result["data"]) > 5


@pytest.mark.asyncio
async def test_live_team_countries():
    result = await get_team_countries()
    assert result["success"] is True
    assert result["results"] > 100


# --- Players ---

@pytest.mark.asyncio
async def test_live_get_players():
    result = await get_players(id=276, season=2024)
    assert result["success"] is True


@pytest.mark.asyncio
async def test_live_player_squads():
    result = await get_player_squads(team=33)
    assert result["success"] is True


@pytest.mark.asyncio
async def test_live_player_seasons():
    result = await get_player_seasons(player=276)
    assert result["success"] is True


@pytest.mark.asyncio
async def test_live_top_scorers():
    result = await get_top_scorers(league=39, season=2024)
    assert result["success"] is True
    assert result["results"] > 0


# --- Fixtures ---

@pytest.mark.asyncio
async def test_live_get_fixtures():
    result = await get_fixtures(team=33, season=2024, last=3)
    assert result["success"] is True
    assert result["results"] == 3


@pytest.mark.asyncio
async def test_live_rounds():
    result = await get_rounds(league=39, season=2024)
    assert result["success"] is True
    assert result["results"] >= 38


@pytest.mark.asyncio
async def test_live_head_to_head():
    result = await get_head_to_head(h2h="33-34", last=5)
    assert result["success"] is True
    assert result["results"] > 0


@pytest.mark.asyncio
async def test_live_fixture_statistics():
    # First get a fixture ID
    fixtures = await get_fixtures(team=33, season=2024, last=1)
    fixture_id = fixtures["data"][0]["fixture"]["id"]
    result = await get_fixture_statistics(fixture=fixture_id)
    assert result["success"] is True


@pytest.mark.asyncio
async def test_live_fixture_events():
    fixtures = await get_fixtures(team=33, season=2024, last=1)
    fixture_id = fixtures["data"][0]["fixture"]["id"]
    result = await get_fixture_events(fixture=fixture_id)
    assert result["success"] is True


# --- Standings ---

@pytest.mark.asyncio
async def test_live_standings():
    result = await get_standings(league=39, season=2024)
    assert result["success"] is True
    assert result["results"] > 0


# --- Coaches ---

@pytest.mark.asyncio
async def test_live_coaches():
    result = await get_coaches(search="Guardiola")
    assert result["success"] is True
    assert result["results"] > 0


# --- Venues ---

@pytest.mark.asyncio
async def test_live_venues():
    result = await get_venues(search="Anfield")
    assert result["success"] is True
    assert result["results"] > 0


# --- Transfers ---

@pytest.mark.asyncio
async def test_live_transfers():
    result = await get_transfers(player=276)
    assert result["success"] is True
    assert result["results"] > 0


# --- Trophies ---

@pytest.mark.asyncio
async def test_live_trophies():
    result = await get_trophies(player=276)
    assert result["success"] is True
    assert result["results"] > 0


# --- Sidelined ---

@pytest.mark.asyncio
async def test_live_sidelined():
    result = await get_sidelined(player=276)
    assert result["success"] is True


# --- Injuries ---

@pytest.mark.asyncio
async def test_live_injuries():
    result = await get_injuries(league=39, season=2024)
    assert result["success"] is True
    assert result["results"] > 0


# --- Predictions ---

@pytest.mark.asyncio
async def test_live_predictions():
    # Get an upcoming fixture
    fixtures = await get_fixtures(league=39, season=2024, next=1)
    if fixtures["results"] > 0:
        fixture_id = fixtures["data"][0]["fixture"]["id"]
        result = await get_predictions(fixture=fixture_id)
        assert result["success"] is True


# --- Odds ---

@pytest.mark.asyncio
async def test_live_bookmakers():
    result = await get_bookmakers()
    assert result["success"] is True
    assert result["results"] > 0


@pytest.mark.asyncio
async def test_live_bet_types():
    result = await get_bet_types()
    assert result["success"] is True
    assert result["results"] > 0


# --- Error handling ---

@pytest.mark.asyncio
async def test_live_search_player_no_league():
    """Searching without league/team falls back to /players/profiles."""
    result = await search_player("Messi")
    assert result["success"] is True
    assert any(p["id"] == 154 for p in result["data"])


@pytest.mark.asyncio
async def test_live_v393_endpoints():
    """Endpoints added in 3.9.2/3.9.3 respond on the live API."""
    from tools.players import get_player_profiles, get_player_teams
    from tools.odds import get_live_bet_types
    from tools.reference import get_api_status

    status = await get_api_status()
    assert status["success"] is True and "subscription" in status["data"]

    profiles = await get_player_profiles(player=1460)
    assert profiles["success"] is True and profiles["data"][0]["player"]["id"] == 1460

    teams = await get_player_teams(1460)
    assert teams["success"] is True and any(t["team"]["id"] == 42 for t in teams["data"])

    bets = await get_live_bet_types()
    assert bets["success"] is True and bets["results"] > 0

    rounds = await get_rounds(39, 2025, dates="true")
    assert rounds["success"] is True and "dates" in rounds["data"][0]

    trophies = await get_trophies(players="276-1100")
    assert trophies["success"] is True


@pytest.mark.asyncio
async def test_live_transfers_no_params():
    """Verify proper error when no params provided."""
    result = await get_transfers()
    assert result["success"] is False


# --- Full workflow ---

@pytest.mark.asyncio
async def test_full_workflow():
    """Test a complete workflow: search team → get stats → get standings."""
    # 1. Search for Liverpool
    teams = await search_team("Liverpool")
    assert teams["success"] is True
    liverpool_id = None
    for t in teams["data"]:
        if t["name"] == "Liverpool" and t["country"] == "England":
            liverpool_id = t["id"]
            break
    assert liverpool_id is not None

    # 2. Get team statistics
    stats = await get_team_statistics(team=liverpool_id, league=39, season=2024)
    assert stats["success"] is True

    # 3. Get league standings
    standings = await get_standings(league=39, season=2024)
    assert standings["success"] is True

    # 4. Get squad
    squad = await get_player_squads(team=liverpool_id)
    assert squad["success"] is True
