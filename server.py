"""API-Football MCP Server — comprehensive MCP server for API-Football v3."""

import argparse
import sys

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "API-Football",
    instructions=(
        "Football/soccer data server powered by API-Football v3. "
        "Use search_team, search_player, search_league, search_coach, or search_venue "
        "to find IDs by name before calling other tools. "
        "Most tools require numeric IDs (team, player, league, fixture). "
        "Season is typically a 4-digit year (e.g., 2024 for the 2024/25 season). "
        "Common league IDs: 39=Premier League, 140=La Liga, 135=Serie A, 78=Bundesliga, 61=Ligue 1, "
        "2=Champions League, 3=Europa League. "
        "For automatic discovery of the best upcoming pre-match opportunities, call scan_best_bets first; "
        "it scans a quota-limited fixture batch, ranks primary picks and keeps NO_BET/insufficient-data "
        "matches visible. For one fixture, use analyze_match and predict_match_bet. "
        "For an in-progress fixture, use predict_live_match_bet; the live model is separate from pre-match. "
        "For historical probability-quality evaluation, use backtest_league. "
        "All betting probabilities are experimental and unvalidated: never describe a pick as a proven "
        "profitable bet or imply VALUE_BET is enabled. Explain missing odds/data and uncertainty."
    ),
    host="0.0.0.0",
    port=8111,
)

# Ensure this module is available as 'server' in sys.modules even when run as __main__,
# so that tool modules doing 'from server import mcp' get the same mcp instance.
if __name__ == "__main__" and "server" not in sys.modules:
    sys.modules["server"] = sys.modules[__name__]


def register_tools():
    """Register all tools — called after mcp is created to avoid circular imports."""
    import tools  # noqa: F401


def main():
    parser = argparse.ArgumentParser(description="API-Football MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="streamable-http",
        help="Transport protocol (stdio or authenticated streamable-http)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8111, help="Port to bind to (default: 8111)")
    args = parser.parse_args()

    mcp._host = args.host
    mcp._port = args.port

    register_tools()

    print(f"Starting API-Football MCP Server on {args.host}:{args.port} ({args.transport})")
    if args.transport == "streamable-http":
        # Wrap the Starlette app with raw ASGI middleware. BaseHTTPMiddleware is
        # intentionally avoided because MCP streaming responses require ASGI passthrough.
        import uvicorn

        from mcp_auth import MCPBearerAuthMiddleware

        app = MCPBearerAuthMiddleware(mcp.streamable_http_app())
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    else:
        # stdio remains protected by the local process boundary. The legacy
        # unauthenticated SSE transport is deliberately not exposed.
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
