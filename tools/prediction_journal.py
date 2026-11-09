"""Persistent, auditable journal for pre-match forecast snapshots.

Set PREDICTION_JOURNAL_DB_PATH to a durable SQLite path before enabling this
module in production. Render's default filesystem is ephemeral; do not point
this at the repository/container filesystem and assume records will survive.
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from server import mcp


SCHEMA_VERSION = 1
MODEL_VALIDATION_DEFAULT = False


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db_path() -> str | None:
    value = os.environ.get("PREDICTION_JOURNAL_DB_PATH", "").strip()
    return value or None


def _connect() -> sqlite3.Connection | None:
    path = _db_path()
    if not path:
        return None
    parent = Path(path).expanduser().parent
    parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(Path(path).expanduser()), timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 15000")
    connection.execute("PRAGMA journal_mode = WAL")
    _initialize(connection)
    return connection


def _initialize(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS prediction_snapshots (
            id TEXT PRIMARY KEY,
            captured_at TEXT NOT NULL,
            mode TEXT NOT NULL,
            data_source TEXT,
            fixture_id TEXT,
            league_id TEXT,
            league_name TEXT,
            season INTEGER,
            kickoff_at TEXT,
            home_team TEXT,
            away_team TEXT,
            model_version TEXT,
            model_validated INTEGER NOT NULL DEFAULT 0,
            payload_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_prediction_snapshots_fixture
            ON prediction_snapshots(fixture_id, captured_at);
        CREATE TABLE IF NOT EXISTS prediction_candidates (
            id TEXT PRIMARY KEY,
            snapshot_id TEXT NOT NULL REFERENCES prediction_snapshots(id),
            market TEXT,
            selection TEXT,
            model_probability REAL,
            fair_odds REAL,
            status TEXT,
            bookmaker TEXT,
            initial_odds REAL,
            odds_source TEXT,
            odds_observed_at TEXT,
            provider_updated_at TEXT,
            outcome TEXT,
            actual_score TEXT,
            settled_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_prediction_candidates_status
            ON prediction_candidates(status);
        CREATE INDEX IF NOT EXISTS idx_prediction_candidates_snapshot
            ON prediction_candidates(snapshot_id);
        CREATE TABLE IF NOT EXISTS prediction_odds_history (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL REFERENCES prediction_candidates(id),
            bookmaker TEXT NOT NULL,
            decimal_odds REAL NOT NULL,
            source TEXT NOT NULL,
            captured_at TEXT NOT NULL,
            provider_updated_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_prediction_odds_candidate
            ON prediction_odds_history(candidate_id, captured_at);
        CREATE TABLE IF NOT EXISTS journal_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        INSERT OR REPLACE INTO journal_metadata(key, value)
            VALUES ('schema_version', '1');
        """
    )
    connection.commit()


def _float_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def _team_name(team: Any) -> str | None:
    if isinstance(team, dict):
        return team.get("name") or team.get("home_name") or team.get("away_name")
    return team if isinstance(team, str) else None


def record_scan_reports(
    reports: list[dict[str, Any]],
    *,
    data_source: str | None = None,
    mode: str = "PREMATCH",
) -> dict[str, Any]:
    """Append every match/candidate from a scan as an immutable forecast snapshot."""
    path = _db_path()
    if not path:
        return {
            "enabled": False, "recorded": 0,
            "reason": "PREDICTION_JOURNAL_DB_PATH is not configured; no persistent journal writes occurred.",
        }
    connection = _connect()
    if connection is None:
        return {"enabled": False, "recorded": 0, "reason": "Journal database is not configured."}
    captured_at = _utc_now()
    recorded = 0
    try:
        with connection:
            for report in reports:
                fixture = report.get("fixture") or {}
                teams = fixture.get("teams") or {}
                league = fixture.get("league") or {}
                home = teams.get("home") or teams.get("home_name")
                away = teams.get("away") or teams.get("away_name")
                forecast = report.get("forecast") or {}
                model_version = (
                    report.get("model") or forecast.get("model")
                    or report.get("model_version") or "unknown"
                )
                snapshot_id = str(uuid.uuid4())
                connection.execute(
                    """INSERT INTO prediction_snapshots
                    (id,captured_at,mode,data_source,fixture_id,league_id,league_name,
                     season,kickoff_at,home_team,away_team,model_version,model_validated,payload_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        snapshot_id, captured_at, mode,
                        data_source or report.get("data_source") or "unknown",
                        str(fixture.get("id")) if fixture.get("id") is not None else None,
                        str(league.get("id")) if league.get("id") is not None else None,
                        league.get("name"),
                        league.get("season") if isinstance(league.get("season"), int) else None,
                        fixture.get("date"),
                        _team_name(home), _team_name(away), str(model_version),
                        int(bool(report.get("model_validated", forecast.get("validated", False)))),
                        json.dumps(report, ensure_ascii=False, separators=(",", ":"), default=str),
                    ),
                )
                candidates = (
                    report.get("candidates")
                    or report.get("forecast_candidates")
                    or forecast.get("candidates")
                    or []
                )
                for candidate in candidates:
                    candidate_id = str(uuid.uuid4())
                    odds = _float_or_none(candidate.get("odds"))
                    bookmaker = candidate.get("bookmaker")
                    odds_source = candidate.get("odds_source") or report.get("odds_source")
                    observed_at = captured_at if odds is not None else None
                    connection.execute(
                        """INSERT INTO prediction_candidates
                        (id,snapshot_id,market,selection,model_probability,fair_odds,status,
                         bookmaker,initial_odds,odds_source,odds_observed_at,provider_updated_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            candidate_id, snapshot_id, candidate.get("market"),
                            candidate.get("selection"),
                            _float_or_none(candidate.get("model_probability")),
                            _float_or_none(candidate.get("fair_odds")),
                            candidate.get("status"), bookmaker, odds, odds_source,
                            observed_at, candidate.get("provider_updated_at"),
                        ),
                    )
                    if odds is not None and odds > 1.0 and bookmaker:
                        connection.execute(
                            """INSERT INTO prediction_odds_history
                            (id,candidate_id,bookmaker,decimal_odds,source,captured_at,provider_updated_at)
                            VALUES (?,?,?,?,?,?,?)""",
                            (
                                str(uuid.uuid4()), candidate_id, str(bookmaker), odds,
                                str(odds_source or "scan_observation"), captured_at,
                                candidate.get("provider_updated_at"),
                            ),
                        )
                recorded += 1
        return {"enabled": True, "recorded": recorded, "captured_at": captured_at}
    finally:
        connection.close()


@mcp.tool()
async def get_prediction_journal_status() -> dict[str, Any]:
    """Report whether the prediction journal is configured and how many records it contains."""
    path = _db_path()
    if not path:
        return {
            "success": True, "enabled": False, "durability": "NOT_CONFIGURED",
            "reason": "Set PREDICTION_JOURNAL_DB_PATH to a durable storage path. Render's default filesystem is ephemeral.",
        }
    connection = _connect()
    if connection is None:
        return {"success": False, "enabled": False, "reason": "Journal database is unavailable."}
    try:
        snapshots = connection.execute("SELECT COUNT(*) FROM prediction_snapshots").fetchone()[0]
        candidates = connection.execute("SELECT COUNT(*) FROM prediction_candidates").fetchone()[0]
        odds = connection.execute("SELECT COUNT(*) FROM prediction_odds_history").fetchone()[0]
        return {
            "success": True, "enabled": True, "durability": "PATH_CONFIGURED_NOT_VERIFIED",
            "database_path": path, "snapshots": snapshots,
            "candidates": candidates, "odds_observations": odds,
            "note": "A configured path is not proof of durable storage; verify that it is on a persistent disk or managed database.",
        }
    finally:
        connection.close()


@mcp.tool()
async def list_prediction_journal(
    limit: int = 50,
    fixture_id: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """List recent immutable forecast candidates, optionally filtered by fixture or status."""
    if not 1 <= limit <= 200:
        return {"success": False, "error": "limit must be between 1 and 200."}
    connection = _connect()
    if connection is None:
        return {"success": False, "enabled": False, "error": "Prediction journal is not configured."}
    try:
        clauses, params = [], []
        if fixture_id:
            clauses.append("s.fixture_id = ?")
            params.append(str(fixture_id))
        if status:
            clauses.append("c.status = ?")
            params.append(status.upper())
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = connection.execute(
            f"""SELECT c.id AS candidate_id,c.market,c.selection,c.model_probability,
                       c.fair_odds,c.status,c.bookmaker,c.initial_odds,c.outcome,
                       c.actual_score,c.settled_at,s.id AS snapshot_id,s.captured_at,
                       s.mode,s.data_source,s.fixture_id,s.league_name,s.kickoff_at,
                       s.home_team,s.away_team,s.model_version,s.model_validated
                FROM prediction_candidates c
                JOIN prediction_snapshots s ON s.id = c.snapshot_id
                {where}
                ORDER BY s.captured_at DESC LIMIT ?""",
            (*params, limit),
        ).fetchall()
        return {"success": True, "count": len(rows), "items": [dict(row) for row in rows]}
    finally:
        connection.close()


@mcp.tool()
async def add_prediction_odds(
    candidate_id: str,
    bookmaker: str,
    odds: float,
    source: str = "manual",
    captured_at: str | None = None,
    provider_updated_at: str | None = None,
) -> dict[str, Any]:
    """Append a timestamped bookmaker price to an existing forecast candidate."""
    if not candidate_id.strip() or not bookmaker.strip() or not source.strip():
        return {"success": False, "error": "candidate_id, bookmaker and source are required."}
    if not odds > 1.0:
        return {"success": False, "error": "Decimal odds must be greater than 1.0."}
    timestamp = captured_at or _utc_now()
    try:
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if provider_updated_at:
            datetime.fromisoformat(provider_updated_at.replace("Z", "+00:00"))
    except ValueError:
        return {"success": False, "error": "Timestamps must be ISO-8601."}
    connection = _connect()
    if connection is None:
        return {"success": False, "enabled": False, "error": "Prediction journal is not configured."}
    try:
        exists = connection.execute(
            "SELECT 1 FROM prediction_candidates WHERE id = ?", (candidate_id,)
        ).fetchone()
        if not exists:
            return {"success": False, "error": "candidate_id was not found."}
        observation_id = str(uuid.uuid4())
        with connection:
            connection.execute(
                """INSERT INTO prediction_odds_history
                (id,candidate_id,bookmaker,decimal_odds,source,captured_at,provider_updated_at)
                VALUES (?,?,?,?,?,?,?)""",
                (observation_id, candidate_id, bookmaker, float(odds), source,
                 timestamp, provider_updated_at),
            )
        return {"success": True, "observation_id": observation_id, "captured_at": timestamp}
    finally:
        connection.close()


@mcp.tool()
async def settle_prediction_candidate(
    candidate_id: str,
    outcome: str,
    actual_score: str | None = None,
    settled_at: str | None = None,
) -> dict[str, Any]:
    """Settle a logged selection as won, lost, push or void for later performance analysis."""
    normalized = outcome.strip().lower()
    if normalized not in {"won", "lost", "push", "void"}:
        return {"success": False, "error": "outcome must be won, lost, push or void."}
    timestamp = settled_at or _utc_now()
    try:
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return {"success": False, "error": "settled_at must be ISO-8601."}
    connection = _connect()
    if connection is None:
        return {"success": False, "enabled": False, "error": "Prediction journal is not configured."}
    try:
        with connection:
            cursor = connection.execute(
                """UPDATE prediction_candidates
                   SET outcome=?,actual_score=?,settled_at=?
                   WHERE id=?""",
                (normalized, actual_score, timestamp, candidate_id),
            )
        if cursor.rowcount == 0:
            return {"success": False, "error": "candidate_id was not found."}
        return {"success": True, "candidate_id": candidate_id, "outcome": normalized, "settled_at": timestamp}
    finally:
        connection.close()
