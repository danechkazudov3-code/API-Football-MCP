"""Bearer-token protection for the public Streamable HTTP MCP endpoint."""

from __future__ import annotations

import hmac
import json
import os
from typing import Any

from starlette.types import ASGIApp, Receive, Scope, Send


class MCPBearerAuthMiddleware:
    """Require MCP_AUTH_TOKEN for HTTP requests to /mcp.

    Other application routes are left to their own authentication policies.
    The token is read for each request so secret rotation does not require
    rebuilding the application object.
    """

    def __init__(self, app: ASGIApp, token_env: str = "MCP_AUTH_TOKEN") -> None:
        self.app = app
        self.token_env = token_env

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http" or scope.get("path", "").rstrip("/") != "/mcp":
            await self.app(scope, receive, send)
            return

        expected = os.environ.get(self.token_env, "").strip()
        if not expected:
            await self._reject(
                send,
                status=503,
                error="MCP authentication is not configured on this server.",
            )
            return

        authorization = next(
            (
                value.decode("latin-1")
                for key, value in scope.get("headers", [])
                if key.lower() == b"authorization"
            ),
            "",
        )
        scheme, separator, supplied = authorization.partition(" ")
        if (
            not separator
            or scheme.lower() != "bearer"
            or not supplied
            or not hmac.compare_digest(supplied.strip(), expected)
        ):
            await self._reject(send, status=401, error="A valid Bearer token is required.")
            return

        await self.app(scope, receive, send)

    @staticmethod
    async def _reject(send: Send, *, status: int, error: str) -> None:
        body = json.dumps({"success": False, "error": error}).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"cache-control", b"no-store"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
