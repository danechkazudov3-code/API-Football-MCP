"""Historical match data adapter for Football-Data.co.uk CSV files."""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime, date
from typing import Any

import httpx

BASE_URL = "https://www.football-data.co.uk/mmz4281"
DIVISIONS = {140: "SP1"}  # La Liga
SOURCE_NAME = "football-data.co.uk"


def _team_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").strip().lower())


def _number(row: dict[str, str], key: str) -> float | None:
    raw = (row.get(key) or "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if value > 1.0 else None


def parse_football_data_csv(
    content: str,
    *,
    league_id: int,
    from_date: str,
    to_date: str,
) -> list[dict[str, Any]]:
    """Convert Football-Data.co.uk rows into API-Football-like finished fixtures."""
    start, end = date.fromisoformat(from_date), date.fromisoformat(to_date)
    reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")))
    required = {"Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"}
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        raise ValueError("CSV schema mismatch: required match result columns are missing.")

    parsed: list[tuple[date, dict[str, str], int, int]] = []
    team_names: set[str] = set()
    for row in reader:
        try:
            match_date = datetime.strptime((row.get("Date") or "").strip(), "%d/%m/%y").date()
            home_goals = int(row["FTHG"])
            away_goals = int(row["FTAG"])
        except (ValueError, TypeError, KeyError):
            continue
        home_name = (row.get("HomeTeam") or "").strip()
        away_name = (row.get("AwayTeam") or "").strip()
        if not home_name or not away_name or not (start <= match_date <= end):
            continue
        parsed.append((match_date, row, home_goals, away_goals))
        team_names.update((home_name, away_name))

    team_ids = {name: index + 1 for index, name in enumerate(sorted(team_names, key=_team_key))}
    fixtures: list[dict[str, Any]] = []
    for index, (match_date, row, home_goals, away_goals) in enumerate(
        sorted(parsed, key=lambda item: item[0]), start=1
    ):
        home_name = row["HomeTeam"].strip()
        away_name = row["AwayTeam"].strip()
        odds = {
            "home": _number(row, "BbAvH"),
            "draw": _number(row, "BbAvD"),
            "away": _number(row, "BbAvA"),
            "source": "Football-Data.co.uk bookmaker average closing odds",
        }
        fixtures.append({
            "fixture": {
                "id": index,
                "date": datetime.combine(match_date, datetime.min.time()).isoformat() + "Z",
                "status": {"short": "FT"},
            },
            "league": {"id": league_id, "name": "La Liga"},
            "teams": {
                "home": {"id": team_ids[home_name], "name": home_name},
                "away": {"id": team_ids[away_name], "name": away_name},
            },
            "goals": {"home": home_goals, "away": away_goals},
            "historical_odds": odds,
            "data_source": SOURCE_NAME,
        })
    return fixtures


async def fetch_football_data_fixtures(
    *,
    league_id: int,
    season: int,
    from_date: str,
    to_date: str,
) -> dict[str, Any]:
    """Fetch one season/division CSV and return normalized finished fixtures."""
    division = DIVISIONS.get(league_id)
    if not division:
        return {
            "success": False,
            "error": f"Football-Data.co.uk mapping is not configured for league_id={league_id}.",
        }
    if season < 1993 or season > 2098:
        return {"success": False, "error": "Season must be a four-digit starting year."}
    season_code = f"{season % 100:02d}{(season + 1) % 100:02d}"
    url = f"{BASE_URL}/{season_code}/{division}.csv"
    try:
        async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": "MyAnalytics-Football/1.0"})
            response.raise_for_status()
        try:
            content = response.content.decode("utf-8-sig")
        except UnicodeDecodeError:
            content = response.content.decode("latin-1")
        fixtures = parse_football_data_csv(
            content, league_id=league_id, from_date=from_date, to_date=to_date
        )
    except httpx.HTTPStatusError as exc:
        return {
            "success": False,
            "error": f"Historical CSV returned HTTP {exc.response.status_code}.",
            "source": SOURCE_NAME,
            "url": url,
        }
    except (httpx.HTTPError, ValueError) as exc:
        return {"success": False, "error": f"Could not load historical CSV: {exc}", "source": SOURCE_NAME, "url": url}
    return {
        "success": True,
        "source": SOURCE_NAME,
        "url": url,
        "data": fixtures,
        "fixtures_count": len(fixtures),
        "odds_available": sum(
            all((item.get("historical_odds") or {}).get(key) for key in ("home", "draw", "away"))
            for item in fixtures
        ),
    }
