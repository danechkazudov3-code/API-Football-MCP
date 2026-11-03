"""Fixture tools: matches, rounds, H2H, stats, events, lineups, player stats."""

from __future__ import annotations

from api_client import api_request, require_params, _error_response

import sys
sys.path.insert(0, ".")
from server import mcp


@mcp.tool()
async def get_fixtures(
    id: int | None = None,
    ids: str | None = None,
    live: str | None = None,
    date: str | None = None,
    league: int | None = None,
    season: int | None = None,
    team: int | None = None,
    last: int | None = None,
    next: int | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    round: str | None = None,
    status: str | None = None,
    venue: int | None = None,
    timezone: str | None = None,
) -> dict:
    """Get fixtures (matches).

    Args:
        id: Fixture ID for a specific match
        ids: Multiple fixture IDs separated by dashes (e.g., '123-456-789', max 20)
        live: Get live matches — 'all' or league IDs separated by dashes
        date: Matches on a specific date (YYYY-MM-DD)
        league: League ID (requires season)
        season: Season year (requires league)
        team: Team ID
        last: Last N finished matches for a team/league
        next: Next N upcoming matches for a team/league
        from_date: Start date range (YYYY-MM-DD, requires league+season)
        to_date: End date range (YYYY-MM-DD, requires league+season)
        round: Round name (e.g., 'Regular Season - 1', requires league+season)
        status: Match status codes separated by dashes (e.g., 'NS-1H-HT-2H-FT')
        venue: Venue ID of the fixture (combine with another filter, e.g. season+team)
        timezone: Timezone for match times (e.g., 'Europe/London')

    Using 'ids' returns events, lineups, statistics and player stats for each
    fixture in one call. Responses include 'extra' (added time per half) and
    'standings' (whether the competition covers standings).

    Returns fixture details: teams, scores, venue, date, status, and more.
    """
    params = {
        "id": id, "ids": ids, "live": live, "date": date,
        "league": league, "season": season, "team": team,
        "last": last, "next": next, "from": from_date, "to": to_date,
        "round": round, "status": status, "venue": venue, "timezone": timezone,
    }
    return await api_request("/fixtures", params)


@mcp.tool()
async def get_rounds(
    league: int,
    season: int,
    current: str | None = None,
    dates: str | None = None,
    timezone: str | None = None,
) -> dict:
    """Get available rounds for a league and season.

    Args:
        league: League ID (required)
        season: Season year (required)
        current: 'true' to get only the current round
        dates: 'true' to include the dates of each round in the response
        timezone: Timezone used for the round dates (e.g., 'Europe/London')

    Returns list of round names (e.g., 'Regular Season - 1', 'Quarter-finals').
    With dates='true', each item is {"round": ..., "dates": ["YYYY-MM-DD", ...]}.
    """
    err = require_params(["league", "season"], {"league": league, "season": season})
    if err:
        return _error_response(err)
    return await api_request("/fixtures/rounds", {
        "league": league, "season": season, "current": current,
        "dates": dates, "timezone": timezone,
    })


@mcp.tool()
async def get_head_to_head(
    h2h: str,
    date: str | None = None,
    league: int | None = None,
    season: int | None = None,
    last: int | None = None,
    next: int | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    status: str | None = None,
    venue: int | None = None,
    timezone: str | None = None,
) -> dict:
    """Get head-to-head fixtures between two teams.

    Args:
        h2h: Two team IDs separated by a dash (e.g., '33-34' for Man Utd vs Man City). Required.
        date: Filter by date (YYYY-MM-DD)
        league: Filter by league ID
        season: Filter by season year
        last: Last N matches
        next: Next N matches
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        status: Match status codes separated by dashes (e.g., 'FT-AET-PEN')
        venue: Filter by venue ID
        timezone: Timezone for match times

    Returns all historical and upcoming matches between the two teams.
    """
    err = require_params(["h2h"], {"h2h": h2h})
    if err:
        return _error_response(err)
    return await api_request("/fixtures/headtohead", {
        "h2h": h2h, "date": date, "league": league, "season": season,
        "last": last, "next": next, "from": from_date, "to": to_date,
        "status": status, "venue": venue, "timezone": timezone,
    })


@mcp.tool()
async def get_fixture_statistics(
    fixture: int,
    team: int | None = None,
    type: str | None = None,
    half: str | None = None,
) -> dict:
    """Get match statistics for a fixture.

    Args:
        fixture: Fixture ID (required)
        team: Team ID to filter stats for one team
        type: Stat type filter (e.g., 'Shots on Goal', 'Ball Possession')
        half: 'true' to also return first/second half stats
              (adds 'statistics_1h' and 'statistics_2h' per team)

    Returns stats like shots, possession, passes, fouls, corners, offsides, expected goals, etc.
    """
    err = require_params(["fixture"], {"fixture": fixture})
    if err:
        return _error_response(err)
    return await api_request("/fixtures/statistics", {
        "fixture": fixture, "team": team, "type": type, "half": half,
    })


@mcp.tool()
async def get_fixture_events(
    fixture: int,
    team: int | None = None,
    player: int | None = None,
    type: str | None = None,
) -> dict:
    """Get match events (goals, cards, substitutions) for a fixture.

    Args:
        fixture: Fixture ID (required)
        team: Filter events by team ID
        player: Filter events by player ID
        type: Event type filter ('Goal', 'Card', 'subst', 'Var')

    Returns chronological list of match events with time, team, player, and details.
    """
    err = require_params(["fixture"], {"fixture": fixture})
    if err:
        return _error_response(err)
    return await api_request("/fixtures/events", {
        "fixture": fixture, "team": team, "player": player, "type": type,
    })


@mcp.tool()
async def get_fixture_lineups(
    fixture: int,
    team: int | None = None,
    player: int | None = None,
    type: str | None = None,
) -> dict:
    """Get team lineups for a fixture.

    Args:
        fixture: Fixture ID (required)
        team: Filter by team ID
        player: Filter by player ID
        type: Filter type

    Returns starting XI, substitutes, coach, and formation for each team.
    """
    err = require_params(["fixture"], {"fixture": fixture})
    if err:
        return _error_response(err)
    return await api_request("/fixtures/lineups", {
        "fixture": fixture, "team": team, "player": player, "type": type,
    })


@mcp.tool()
async def get_fixture_player_stats(
    fixture: int,
    team: int | None = None,
) -> dict:
    """Get detailed player statistics for a fixture.

    Args:
        fixture: Fixture ID (required)
        team: Filter by team ID

    Returns per-player stats: minutes played, rating, shots, goals, passes,
    tackles, duels, dribbles, fouls, cards, and more.
    """
    err = require_params(["fixture"], {"fixture": fixture})
    if err:
        return _error_response(err)
    return await api_request("/fixtures/players", {
        "fixture": fixture, "team": team,
    })
