"""Unit tests for the aggregated match analyzer."""
import sys
import pytest
from tests.conftest import mock_httpx_response

sys.argv = ["test"]
from server import register_tools
register_tools()
from tools.analyzer import analyze_match, _summarize_team_form, _summarize_head_to_head


def _fixture(fixture_id=9001):
    return {
        "fixture": {"id": fixture_id, "date": "2026-11-10T20:00:00+00:00",
                    "status": {"short": "NS", "long": "Not Started"},
                    "venue": {"name": "Test Stadium"}},
        "league": {"id": 39, "name": "Premier League"},
        "teams": {"home": {"id": 10, "name": "Home FC"},
                  "away": {"id": 20, "name": "Away FC"}},
        "goals": {"home": None, "away": None}, "score": {},
    }


def _played_fixture(team_id, opponent_id, date, team_goals, opponent_goals, home=True):
    home_team = {"id": team_id, "name": "Test FC"} if home else {"id": opponent_id, "name": "Opponent"}
    away_team = {"id": opponent_id, "name": "Opponent"} if home else {"id": team_id, "name": "Test FC"}
    home_goals, away_goals = (team_goals, opponent_goals) if home else (opponent_goals, team_goals)
    return {"fixture": {"date": date, "status": {"short": "FT"}},
            "teams": {"home": home_team, "away": away_team},
            "goals": {"home": home_goals, "away": away_goals}}


def _team_stats():
    return {"league": {"id": 39}, "goals": {
        "for": {"average": {"home": "1.8", "away": "1.2"}},
        "against": {"average": {"home": "0.8", "away": "1.3"}},
    }}


def _standings():
    return {"league": {"standings": [[
        {"all": {"played": 10, "goals": {"for": 20}}},
        {"all": {"played": 10, "goals": {"for": 10}}},
    ]]}}


def test_summarize_team_form_counts_results_and_orders_matches():
    result = {"success": True, "data": [
        _played_fixture(10, 99, "2026-11-03", 2, 0),
        _played_fixture(10, 98, "2026-11-01", 1, 1),
        _played_fixture(10, 97, "2026-11-02", 0, 1),
        {"fixture": {"date": "2026-11-04", "status": {"short": "NS"}},
         "teams": {"home": {"id": 10}, "away": {"id": 96}},
         "goals": {"home": None, "away": None}},
    ]}
    summary = _summarize_team_form(10, "Test FC", result)
    assert summary["available"] is True
    assert summary["matches_played"] == 3
    assert summary["form"] == "DLW"
    assert (summary["wins"], summary["draws"], summary["losses"]) == (1, 1, 1)
    assert (summary["goals_scored"], summary["goals_conceded"]) == (3, 2)
    assert [match["date"] for match in summary["matches"]] == ["2026-11-01", "2026-11-02", "2026-11-03"]
    assert summary["venue_splits"]["home"]["available"] is True
    assert summary["venue_splits"]["away"]["matches_played"] == 0


def test_head_to_head_counts_results_for_current_home_and_away_teams():
    result = {"success": True, "data": [
        _played_fixture(20, 10, "2026-10-01", 1, 2, home=True),
        _played_fixture(10, 20, "2026-09-01", 0, 1, home=True),
    ]}
    summary = _summarize_head_to_head(result, home_team_id=10, away_team_id=20)
    assert summary["current_home_team_wins"] == 1
    assert summary["current_away_team_wins"] == 1
    assert summary["draws"] == 0


@pytest.mark.asyncio
async def test_analyze_match_rejects_invalid_fixture_id(mock_api):
    result = await analyze_match(0)
    assert result["success"] is False
    assert "fixture_id" in result["error"]
    mock_api.assert_not_called()


@pytest.mark.asyncio
async def test_analyze_match_fixture_not_found(mock_api):
    mock_api.return_value = mock_httpx_response(data=[])
    result = await analyze_match(9001)
    assert result["success"] is False
    assert "Fixture not found" in result["error"]


@pytest.mark.asyncio
async def test_analyze_match_uses_league_and_venue_adjustments(mock_api):
    home_matches = [_played_fixture(10, 11, "2026-11-01", 2, 0),
                    _played_fixture(10, 12, "2026-11-05", 1, 1)]
    away_matches = [_played_fixture(20, 21, "2026-11-02", 0, 1, home=False),
                    _played_fixture(20, 22, "2026-11-06", 2, 1, home=False)]
    mock_api.side_effect = [
        mock_httpx_response(data=[_fixture()]),
        mock_httpx_response(data=home_matches),
        mock_httpx_response(data=away_matches),
        mock_httpx_response(data=[]),  # H2H
        mock_httpx_response(data=[]),  # injuries
        mock_httpx_response(data=[_team_stats()]),
        mock_httpx_response(data=[_team_stats()]),
        mock_httpx_response(data=[_standings()]),
    ]
    result = await analyze_match(9001)
    assert result["success"] is True
    assert result["analysis_status"] == "LEAGUE_ADJUSTED"
    assert result["fixture"]["id"] == 9001
    assert result["recent_form"]["home"]["form"] == "WD"
    assert result["recent_form"]["away"]["form"] == "LW"
    assert result["forecast"]["goal_rates"]["method"] == "league_normalized_venue_attack_defence"
    assert result["head_to_head"]["available"] is False
    assert result["injuries"]["available"] is True
    assert mock_api.await_count == 8


@pytest.mark.asyncio
async def test_analyze_match_falls_back_when_season_stats_are_unavailable(mock_api):
    mock_api.side_effect = [
        mock_httpx_response(data=[_fixture()]),
        mock_httpx_response(data=[_played_fixture(10, 11, "2026-11-01", 2, 0)]),
        mock_httpx_response(data=[_played_fixture(20, 21, "2026-11-02", 0, 1, home=False)]),
        mock_httpx_response(data=[]),  # H2H
        mock_httpx_response(data=[]),  # injuries
        mock_httpx_response(errors={"team": "stats unavailable"}),
        mock_httpx_response(errors={"team": "stats unavailable"}),
        mock_httpx_response(errors={"league": "standings unavailable"}),
    ]
    result = await analyze_match(9001)
    assert result["success"] is True
    assert result["analysis_status"] == "DATA_COLLECTION_WITH_FORM"
    assert result["forecast"]["goal_rates"]["method"] == "shrunk_recent_form_with_home_advantage"
