"""Unit tests for the aggregated match analyzer."""

import sys

import pytest

from tests.conftest import mock_httpx_response

sys.argv = ["test"]
from server import register_tools

register_tools()

from tools.analyzer import analyze_match, _summarize_team_form


def _fixture(fixture_id=9001):
    return {
        "fixture": {
            "id": fixture_id,
            "date": "2026-11-10T20:00:00+00:00",
            "status": {"short": "NS", "long": "Not Started"},
            "venue": {"name": "Test Stadium"},
        },
        "league": {"id": 39, "name": "Premier League"},
        "teams": {
            "home": {"id": 10, "name": "Home FC"},
            "away": {"id": 20, "name": "Away FC"},
        },
        "goals": {"home": None, "away": None},
        "score": {},
    }


def _played_fixture(team_id, opponent_id, date, team_goals, opponent_goals, home=True):
    home_team = {"id": team_id, "name": "Test FC"} if home else {"id": opponent_id, "name": "Opponent"}
    away_team = {"id": opponent_id, "name": "Opponent"} if home else {"id": team_id, "name": "Test FC"}
    home_goals, away_goals = (team_goals, opponent_goals) if home else (opponent_goals, team_goals)
    return {
        "fixture": {"date": date, "status": {"short": "FT"}},
        "teams": {"home": home_team, "away": away_team},
        "goals": {"home": home_goals, "away": away_goals},
    }


def test_summarize_team_form_counts_results_and_orders_matches():
    result = {
        "success": True,
        "data": [
            _played_fixture(10, 99, "2026-11-03", 2, 0),
            _played_fixture(10, 98, "2026-11-01", 1, 1),
            _played_fixture(10, 97, "2026-11-02", 0, 1),
            {
                "fixture": {"date": "2026-11-04", "status": {"short": "NS"}},
                "teams": {"home": {"id": 10}, "away": {"id": 96}},
                "goals": {"home": None, "away": None},
            },
        ],
    }

    summary = _summarize_team_form(10, "Test FC", result)

    assert summary["available"] is True
    assert summary["matches_played"] == 3
    assert summary["form"] == "DLW"
    assert (summary["wins"], summary["draws"], summary["losses"]) == (1, 1, 1)
    assert (summary["goals_scored"], summary["goals_conceded"]) == (3, 2)
    assert [match["date"] for match in summary["matches"]] == [
        "2026-11-01", "2026-11-02", "2026-11-03"
    ]


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
async def test_analyze_match_collects_fixture_and_both_forms(mock_api):
    home_matches = [
        _played_fixture(10, 11, "2026-11-01", 2, 0),
        _played_fixture(10, 12, "2026-11-05", 1, 1),
    ]
    away_matches = [
        _played_fixture(20, 21, "2026-11-02", 0, 1, home=False),
        _played_fixture(20, 22, "2026-11-06", 2, 1, home=False),
    ]
    mock_api.side_effect = [
        mock_httpx_response(data=[_fixture()]),
        mock_httpx_response(data=home_matches),
        mock_httpx_response(data=away_matches),
    ]

    result = await analyze_match(9001)

    assert result["success"] is True
    assert result["analysis_status"] == "DATA_COLLECTION_WITH_FORM"
    assert result["fixture"]["id"] == 9001
    assert result["recent_form"]["home"]["form"] == "WD"
    assert result["recent_form"]["away"]["form"] == "LW"
    assert result["recent_form"]["home"]["matches_played"] == 2
    assert result["recent_form"]["away"]["matches_played"] == 2
    assert mock_api.await_count == 3


@pytest.mark.asyncio
async def test_analyze_match_reports_partial_form_when_one_request_fails(mock_api):
    mock_api.side_effect = [
        mock_httpx_response(data=[_fixture()]),
        mock_httpx_response(data=[]),
        mock_httpx_response(errors={"team": "Temporary API error"}),
    ]

    result = await analyze_match(9001)

    assert result["success"] is True
    assert result["analysis_status"] == "PARTIAL_DATA_COLLECTION"
    assert result["recent_form"]["home"]["available"] is False
    assert result["recent_form"]["away"]["available"] is False
