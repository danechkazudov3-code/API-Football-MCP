"""Tests for bearer-token protection of the MCP HTTP endpoint."""

import json

import pytest

from mcp_auth import MCPBearerAuthMiddleware


async def _call(app, *, path="/mcp", headers=None):
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "method": "POST",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": headers or [],
        "server": ("testserver", 80),
        "client": ("testclient", 1234),
        "scheme": "http",
    }
    await app(scope, receive, send)
    return sent


@pytest.mark.asyncio
async def test_mcp_without_token_is_rejected(monkeypatch):
    monkeypatch.setenv("MCP_AUTH_TOKEN", "correct-secret")
    called = False

    async def downstream(scope, receive, send):
        nonlocal called
        called = True

    response = await _call(MCPBearerAuthMiddleware(downstream))
    assert response[0]["status"] == 401
    assert not called
    assert json.loads(response[1]["body"])["success"] is False


@pytest.mark.asyncio
async def test_mcp_with_valid_bearer_token_is_forwarded(monkeypatch):
    monkeypatch.setenv("MCP_AUTH_TOKEN", "correct-secret")
    called = False

    async def downstream(scope, receive, send):
        nonlocal called
        called = True

    response = await _call(
        MCPBearerAuthMiddleware(downstream),
        headers=[(b"authorization", b"Bearer correct-secret")],
    )
    assert called
    assert response == []


@pytest.mark.asyncio
async def test_mcp_with_invalid_token_is_rejected(monkeypatch):
    monkeypatch.setenv("MCP_AUTH_TOKEN", "correct-secret")

    async def downstream(scope, receive, send):
        raise AssertionError("Unauthenticated request reached MCP")

    response = await _call(
        MCPBearerAuthMiddleware(downstream),
        headers=[(b"authorization", b"Bearer wrong-secret")],
    )
    assert response[0]["status"] == 401


@pytest.mark.asyncio
async def test_missing_server_secret_fails_closed(monkeypatch):
    monkeypatch.delenv("MCP_AUTH_TOKEN", raising=False)

    async def downstream(scope, receive, send):
        raise AssertionError("Unconfigured MCP endpoint must not be exposed")

    response = await _call(MCPBearerAuthMiddleware(downstream))
    assert response[0]["status"] == 503


@pytest.mark.asyncio
async def test_non_mcp_routes_keep_their_own_auth_policy(monkeypatch):
    monkeypatch.delenv("MCP_AUTH_TOKEN", raising=False)
    called = False

    async def downstream(scope, receive, send):
        nonlocal called
        called = True

    await _call(MCPBearerAuthMiddleware(downstream), path="/tester")
    assert called
