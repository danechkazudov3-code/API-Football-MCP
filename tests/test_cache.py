"""Tests for the in-memory TTL cache and endpoint cache policy."""

from cache import TTLCache, cache_ttl


def test_cache_returns_independent_copies():
    cache = TTLCache()
    cache.set("key", {"success": True, "data": [{"id": 1}]}, 60)
    result = cache.get("key")
    result["data"][0]["id"] = 99
    assert cache.get("key")["data"][0]["id"] == 1


def test_cache_expires_entries(monkeypatch):
    cache = TTLCache()
    now = [100.0]
    monkeypatch.setattr("cache.time.monotonic", lambda: now[0])
    cache.set("key", {"value": 1}, 5)
    assert cache.get("key") == {"value": 1}
    now[0] = 106.0
    assert cache.get("key") is None


def test_cache_enforces_maximum_entries():
    cache = TTLCache(max_entries=2)
    cache.set("a", {"v": 1}, 60)
    cache.set("b", {"v": 2}, 60)
    cache.set("c", {"v": 3}, 60)
    assert len(cache) == 2
    assert cache.get("a") is None
    assert cache.get("b") == {"v": 2}


def test_cache_key_is_stable_for_parameter_order():
    assert TTLCache.make_key("/fixtures", {"team": 1, "last": 5}) == TTLCache.make_key(
        "/fixtures", {"last": 5, "team": 1}
    )


def test_live_and_fixture_id_requests_are_not_cached():
    assert cache_ttl("/odds/live", {"fixture": 123}) == 0
    assert cache_ttl("/fixtures", {"live": "all"}) == 0
    assert cache_ttl("/fixtures", {"ids": "123"}) == 0
    assert cache_ttl("/fixtures", {"id": 123}) == 0


def test_reference_and_historical_ttls():
    assert cache_ttl("/leagues") == 86400
    assert cache_ttl("/standings", {"league": 39, "season": 2026}) == 21600
    assert cache_ttl("/fixtures", {"team": 50, "last": 5}) == 3600
    assert cache_ttl("/fixtures", {"date": "2026-11-09"}) == 60
    assert cache_ttl("/odds", {"fixture": 123}) == 30
    assert cache_ttl("/players", {"id": 1}) == 0
