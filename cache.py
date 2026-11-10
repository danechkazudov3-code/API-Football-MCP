"""Small bounded in-memory TTL cache for successful API-Football responses."""

from __future__ import annotations

import copy
import json
import time
from collections import OrderedDict
from typing import Any


class TTLCache:
    """Process-local cache with expiration and a maximum number of entries."""

    def __init__(self, max_entries: int = 512) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1")
        self.max_entries = max_entries
        self._items: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()

    @staticmethod
    def make_key(endpoint: str, params: dict[str, Any] | None = None) -> str:
        encoded = json.dumps(params or {}, sort_keys=True, separators=(",", ":"), default=str)
        return f"{endpoint}?{encoded}"

    def get(self, key: str) -> dict[str, Any] | None:
        item = self._items.get(key)
        if item is None:
            return None
        expires_at, value = item
        if expires_at <= time.monotonic():
            del self._items[key]
            return None
        self._items.move_to_end(key)
        return copy.deepcopy(value)

    def set(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        self._items[key] = (time.monotonic() + ttl_seconds, copy.deepcopy(value))
        self._items.move_to_end(key)
        while len(self._items) > self.max_entries:
            self._items.popitem(last=False)

    def clear(self) -> None:
        self._items.clear()

    def __len__(self) -> int:
        return len(self._items)


def cache_ttl(endpoint: str, params: dict[str, Any] | None = None) -> int:
    """Return a conservative TTL; volatile/live endpoints are never cached."""
    params = params or {}
    path = endpoint.rstrip("/") or "/"

    if path in {"/odds/live", "/odds/live/bets"}:
        return 0
    if path == "/fixtures":
        if params.get("live") or params.get("id") or params.get("ids"):
            return 0
        if params.get("team") and params.get("last"):
            return 3600
        if params.get("next") or params.get("date"):
            return 60
        return 0
    if path == "/odds":
        return 30
    if path in {
        "/countries", "/leagues", "/seasons", "/timezone",
        "/odds/bookmakers", "/odds/bets",
    }:
        return 86400
    if path in {"/standings", "/teams/statistics"}:
        return 21600
    return 0
