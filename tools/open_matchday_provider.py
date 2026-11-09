"""Open-Matchday CSV fallback for current-season fixtures and recent results.

The upstream dataset is informational/non-commercial, refreshed daily, and does
not provide odds, injuries, lineups, or live scores. Keep those fields explicitly
unavailable rather than fabricating them.
"""
from __future__ import annotations

import asyncio
import csv
import io
from datetime import date
from typing import Any

import httpx

BASE = "https://raw.githubusercontent.com/oladeeayo/open-matchday/master/data"
LEAGUES = {
    39: ("ENG_1_premier-league", "Premier League"),
    140: ("ESP_1_la-liga", "La Liga"),
    135: ("ITA_1_serie-a", "Serie A"),
    78: ("GER_1_bundesliga", "Bundesliga"),
    61: ("FRA_1_ligue-1", "Ligue 1"),
}
SEASON_CODE = "2627"
SOURCE = "open-matchday"


async def _csv_rows(url: str) -> list[dict[str, str]]:
    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
        response = await client.get(url, headers={"User-Agent": "MyAnalytics-Football/1.0"})
        response.raise_for_status()
    return list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))


def _form(team: str, matches: list[dict[str, str]], venue: str | None = None) -> dict[str, Any]:
    selected = []
    for row in matches:
        is_home = row.get("home") == team
        is_away = row.get("away") == team
        if not (is_home or is_away):
            continue
        if venue == "home" and not is_home:
            continue
        if venue == "away" and not is_away:
            continue
        try:
            hg, ag = int(row["ft_home"]), int(row["ft_away"])
        except (KeyError, TypeError, ValueError):
            continue
        scored, conceded = (hg, ag) if is_home else (ag, hg)
        result = "W" if scored > conceded else "D" if scored == conceded else "L"
        selected.append({
            "date": row.get("date"), "opponent": row.get("away") if is_home else row.get("home"),
            "venue": "home" if is_home else "away", "score": f"{scored}-{conceded}",
            "result": result, "scored": scored, "conceded": conceded,
            "stats": {
                "shots": {"for": row.get("home_shots" if is_home else "away_shots"), "against": row.get("away_shots" if is_home else "home_shots")},
                "shots_on_target": {"for": row.get("home_target" if is_home else "away_target"), "against": row.get("away_target" if is_home else "home_target")},
                "fouls": {"for": row.get("home_fouls" if is_home else "away_fouls"), "against": row.get("away_fouls" if is_home else "home_fouls")},
                "corners": {"for": row.get("home_corners" if is_home else "away_corners"), "against": row.get("away_corners" if is_home else "home_corners")},
                "yellow_cards": {"for": row.get("home_yellow" if is_home else "away_yellow"), "against": row.get("away_yellow" if is_home else "home_yellow")},
                "red_cards": {"for": row.get("home_red" if is_home else "away_red"), "against": row.get("away_red" if is_home else "home_red")},
            },
        })
    selected.sort(key=lambda x: x.get("date") or "", reverse=True)
    selected = selected[:10]
    count = len(selected)
    statistics = {}
    for metric in ("shots", "shots_on_target", "fouls", "corners", "yellow_cards", "red_cards"):
        pairs = []
        for match in selected:
            values = (match.get("stats") or {}).get(metric) or {}
            try:
                for_value = float(values.get("for"))
                against_value = float(values.get("against"))
            except (TypeError, ValueError):
                continue
            if for_value >= 0 and against_value >= 0:
                pairs.append((for_value, against_value))
        statistics[metric] = {
            "available": bool(pairs),
            "matches_sampled": len(pairs),
            "average_for": round(sum(pair[0] for pair in pairs) / len(pairs), 2) if pairs else None,
            "average_against": round(sum(pair[1] for pair in pairs) / len(pairs), 2) if pairs else None,
        }
    return {
        "available": count > 0, "team": team, "matches_played": count,
        "statistics": statistics,
        "statistics_note": "Averages use only matches with both values present; missing values are not treated as zero.",
        "form": "".join(x["result"] for x in selected),
        "wins": sum(x["result"] == "W" for x in selected),
        "draws": sum(x["result"] == "D" for x in selected),
        "losses": sum(x["result"] == "L" for x in selected),
        "goals_scored": sum(x["scored"] for x in selected),
        "goals_conceded": sum(x["conceded"] for x in selected),
        "average_goals_scored": round(sum(x["scored"] for x in selected) / count, 2) if count else None,
        "average_goals_conceded": round(sum(x["conceded"] for x in selected) / count, 2) if count else None,
        "matches": [{k: x[k] for k in ("date", "opponent", "venue", "score", "result")} for x in selected],
    }


async def fetch_open_matchday_scan(
    league_id: int | None, start_date: str, end_date: str, max_fixtures: int,
) -> dict[str, Any]:
    if league_id is None:
        parts = await asyncio.gather(*(
            fetch_open_matchday_scan(item_id, start_date, end_date, max_fixtures)
            for item_id in LEAGUES
        ))
        successful = [part for part in parts if part.get("success")]
        fixtures = sorted(
            [fixture for part in successful for fixture in part.get("fixtures", [])],
            key=lambda item: item.get("fixture", {}).get("date") or "",
        )[:max_fixtures]
        return {
            "success": bool(successful),
            "source": SOURCE,
            "fixtures_found_in_window": sum(part.get("fixtures_found_in_window", 0) for part in successful),
            "fixtures": fixtures,
            "historical_results_loaded": sum(part.get("historical_results_loaded", 0) for part in successful),
            "leagues_checked": [part.get("league") for part in successful],
            "data_limitations": [
                "Daily snapshot; not a live data feed.",
                "No bookmaker odds, injuries, confirmed lineups, or live match data.",
                "Recent-form summaries use only completed matches available in this CSV.",
                "Shots, shots on target, fouls and cards are partial; missing values are not zero. No xG is supplied.",
                "Source is provided for informational, non-commercial use; attribution required.",
            ],
            "errors": [part.get("error") for part in parts if not part.get("success")],
        }
    mapping = LEAGUES.get(league_id)
    if not mapping:
        return {"success": False, "error": f"Open-Matchday mapping unavailable for league_id={league_id}."}
    folder, league_name = mapping
    root = f"{BASE}/{folder}"
    try:
        fixtures_rows, result_rows = await asyncio.gather(
            _csv_rows(f"{root}/fixtures_{SEASON_CODE}.csv"),
            _csv_rows(f"{root}/results_{SEASON_CODE}.csv"),
        )
    except (httpx.HTTPError, UnicodeError, csv.Error) as exc:
        return {"success": False, "source": SOURCE, "error": f"Could not load Open-Matchday CSV: {exc}"}

    start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    upcoming = [
        row for row in fixtures_rows
        if row.get("date") and start <= date.fromisoformat(row["date"]) <= end
        and row.get("home") and row.get("away")
    ]
    upcoming.sort(key=lambda row: (row.get("date") or "", row.get("time") or ""))
    upcoming = upcoming[:max_fixtures]
    reports = []
    for row in upcoming:
        kickoff = row.get("date") or ""
        prior = [
            item for item in result_rows
            if item.get("date") and item["date"] < kickoff
            and item.get("ft_home", "").strip() and item.get("ft_away", "").strip()
        ]
        home, away = row["home"], row["away"]
        home_form, away_form = _form(home, prior), _form(away, prior)
        home_venue, away_venue = _form(home, prior, "home"), _form(away, prior, "away")
        model_home = home_venue if home_venue["matches_played"] >= 3 else home_form
        model_away = away_venue if away_venue["matches_played"] >= 3 else away_form
        reports.append({
            "fixture": {
                "id": f"open-matchday:{league_id}:{kickoff}:{home}:{away}",
                "date": f"{kickoff}T{row.get('time') or '00:00'}:00",
                "league": {"id": league_id, "name": league_name, "season": 2026},
                "teams": {"home": {"name": home}, "away": {"name": away},
                          "home_name": home, "away_name": away},
                "round": row.get("gw"),
            },
            "home_form": home_form, "away_form": away_form,
            "home_venue_form": home_venue, "away_venue_form": away_venue,
            "model_home_form": model_home, "model_away_form": model_away,
        })
    return {
        "success": True, "source": SOURCE, "league": league_name,
        "fixtures_found_in_window": len([
            row for row in fixtures_rows
            if row.get("date") and start <= date.fromisoformat(row["date"]) <= end
        ]),
        "fixtures": reports,
        "historical_results_loaded": len(result_rows),
        "data_limitations": [
            "Daily snapshot; not a live data feed.",
            "No bookmaker odds, injuries, confirmed lineups, or live match data.",
            "Recent-form summaries use only completed matches available in this CSV.",
            "Shots, shots on target, fouls and cards are partial; missing values are not zero. No xG is supplied.",
            "Source is provided for informational, non-commercial use; attribution required.",
        ],
    }
