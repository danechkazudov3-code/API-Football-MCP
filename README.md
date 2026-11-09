# API-Football MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server that wraps the [API-Football v3](https://www.api-football.com/) REST API, exposing football/soccer data as MCP tools. Built with Python and [FastMCP](https://github.com/jlowin/fastmcp).

## Features

- 47 MCP tools covering teams, players, fixtures, standings, transfers, odds, automatic pre-match picks, live picks, and historical backtesting
- Streamable HTTP, SSE, and stdio transports
- Async HTTP client with rate-limit tracking and error handling
- Docker support for easy deployment

## Prerequisites

- Python 3.13+
- An API-Football API key (get one at [api-football.com](https://www.api-football.com/))

## Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/API-Football.git
   cd API-Football
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure your API key:**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and add your API-Football key:
   ```
   API_FOOTBALL_KEY=your_api_key_here
   ```

## Running the Server

```bash
# Default: streamable-http on port 8111
python server.py

# Stdio transport (for direct MCP client piping)
python server.py --transport stdio

# SSE transport on a custom port
python server.py --transport sse --port 9000

# Custom host and port
python server.py --host 127.0.0.1 --port 3000
```

The MCP endpoint will be available at `http://localhost:8111/mcp`.

### Docker

```bash
# Using docker compose
docker compose up -d

# Or build and run manually
docker build -t api-football-mcp .
docker run -d -p 8111:8111 --env-file .env --name api-football-mcp api-football-mcp

# Or use the deploy script (builds, runs, and health-checks)
./deploy.sh
```

## MCP Client Configuration

To connect this server to an MCP client, add it to your MCP config:

**Streamable HTTP (remote/Docker):**
```json
{
  "mcpServers": {
    "api-football": {
      "type": "streamable-http",
      "url": "http://localhost:8111/mcp"
    }
  }
}
```

**Stdio (local):**
```json
{
  "mcpServers": {
    "api-football": {
      "type": "stdio",
      "command": "python",
      "args": ["server.py", "--transport", "stdio"],
      "cwd": "/path/to/API-Football",
      "env": {
        "API_FOOTBALL_KEY": "your_api_key_here"
      }
    }
  }
}
```

## Available Tools

### Search / Name Resolution

Use these first to find IDs by name, then pass IDs to other tools.

| Tool | Description |
|------|-------------|
| `search_team` | Search for a team by name (e.g., "Manchester", "Barcelona") |
| `search_player` | Search for a player by name (optionally within a league or team) |
| `search_league` | Search for a league/competition by name |
| `search_coach` | Search for a coach/manager by name |
| `search_venue` | Search for a stadium/venue by name |

### Reference Data

| Tool | Description |
|------|-------------|
| `get_timezones` | List all supported timezones |
| `get_countries` | List or search countries |
| `get_seasons` | List all available seasons |
| `get_leagues` | Get league info by ID, name, country, season, or team |
| `get_api_status` | Account plan and today's request usage (free, doesn't count against quota) |

### Teams

| Tool | Description |
|------|-------------|
| `get_teams` | Get team info by ID, name, league, country, or search |
| `get_team_statistics` | Detailed team stats for a league and season (form, goals, cards, lineups) |
| `get_team_seasons` | List available seasons for a team |
| `get_team_countries` | List all countries with teams |

### Players

| Tool | Description |
|------|-------------|
| `get_players` | Get player info and season statistics |
| `get_player_squads` | Get current squad for a team, or find a player's team |
| `get_player_seasons` | List available seasons for a player |
| `get_player_profiles` | Player bios across all leagues, searchable by last name |
| `get_player_teams` | Every team a player has played for, with seasons |
| `get_top_scorers` | Top goal scorers for a league and season |
| `get_top_assists` | Top assist providers for a league and season |
| `get_top_yellow_cards` | Players with most yellow cards in a league and season |
| `get_top_red_cards` | Players with most red cards in a league and season |

### Fixtures (Matches)

| Tool | Description |
|------|-------------|
| `get_fixtures` | Get matches by ID, date, league, team, live status, or date range |
| `get_rounds` | Get available rounds for a league and season |
| `get_head_to_head` | Head-to-head history between two teams |
| `get_fixture_statistics` | Match stats (shots, possession, passes, corners, etc.) |
| `get_fixture_events` | Match events (goals, cards, substitutions, VAR) |
| `get_fixture_lineups` | Starting XI, substitutes, formation, and coach |
| `get_fixture_player_stats` | Detailed per-player stats for a match |

### Standings

| Tool | Description |
|------|-------------|
| `get_standings` | League table with points, wins, draws, losses, goals, form |

### Coaches

| Tool | Description |
|------|-------------|
| `get_coaches` | Get coach info by ID, team, or search (includes career history) |

### Venues

| Tool | Description |
|------|-------------|
| `get_venues` | Get stadium info by ID, name, city, country, or search |

### Transfers

| Tool | Description |
|------|-------------|
| `get_transfers` | Transfer history for a player or team |

### Trophies

| Tool | Description |
|------|-------------|
| `get_trophies` | Trophies won by a player or coach |

### Sidelined

| Tool | Description |
|------|-------------|
| `get_sidelined` | Injury/absence history for a player or coach |

### Injuries

| Tool | Description |
|------|-------------|
| `get_injuries` | Current injuries filtered by league, team, player, fixture(s), or date |

### Predictions

| Tool | Description |
|------|-------------|
| `get_predictions` | API-Football's match prediction with win/draw probabilities, advice, and team comparison |\n| `predict_match_bet` | Experimental automatic pre-match pick, best returned bookmaker price, fair odds, EV, and visible candidate ranking |\n| `predict_live_match_bet` | Separate in-play model using current score, elapsed time, live shots, red cards, and live odds |\n| `backtest_league` | Chronological walk-forward probability evaluation on historical league fixtures (no ROI without historical odds) |

### Odds

| Tool | Description |
|------|-------------|
| `get_odds` | Pre-match betting odds from various bookmakers |
| `get_live_odds` | Live/in-play betting odds |
| `get_odds_mapping` | List of fixtures with available odds data |
| `get_bookmakers` | List or search available bookmakers |
| `get_bet_types` | List or search available pre-match bet types |
| `get_live_bet_types` | List or search available in-play bet types |

## Common League IDs

| League | ID |
|--------|----|
| Premier League (England) | 39 |
| La Liga (Spain) | 140 |
| Serie A (Italy) | 135 |
| Bundesliga (Germany) | 78 |
| Ligue 1 (France) | 61 |
| Champions League | 2 |
| Europa League | 3 |

## Testing

```bash
# Run unit tests (mocked, no API calls)
pytest tests/ -v --ignore=tests/test_integration.py

# Run a single test file
pytest tests/test_teams.py -v

# Run a single test
pytest tests/test_teams.py::test_get_teams_by_id -v

# Run integration tests (uses live API, counts against daily limit)
pytest tests/test_integration.py -v
```

## Project Structure

```
API-Football/
├── server.py           # MCP server entrypoint (FastMCP instance + CLI)
├── api_client.py       # Shared async HTTP client, auth, error handling
├── tools/              # MCP tool modules (one per API domain)
│   ├── __init__.py     # Bulk-registers all tool modules
│   ├── search.py       # Name→ID resolution tools
│   ├── reference.py    # Timezones, countries, seasons, leagues
│   ├── teams.py        # Team info and statistics
│   ├── players.py      # Player info, squads, top scorers/assists/cards
│   ├── fixtures.py     # Matches, H2H, stats, events, lineups
│   ├── standings.py    # League tables
│   ├── coaches.py      # Coach info and career history
│   ├── venues.py       # Stadium info
│   ├── transfers.py    # Transfer history
│   ├── trophies.py     # Player/coach trophies
│   ├── sidelined.py    # Injury/absence history
│   ├── injuries.py     # Current injuries
│   ├── predictions.py  # Match predictions
│   └── odds.py         # Betting odds, bookmakers, bet types
├── tests/              # Test suite
│   ├── conftest.py     # Shared fixtures and mock helpers
│   ├── test_*.py       # Unit tests (mocked)
│   └── test_integration.py  # Live API integration tests
├── .env.example        # Environment variable template
├── Dockerfile          # Container image definition
├── docker-compose.yml  # Docker compose config
├── deploy.sh           # Build + deploy + health-check script
└── requirements.txt    # Python dependencies
```

## License

MIT


## MyAnalytics Prediction Engine

The prediction engine requirements and implementation roadmap are documented in [`docs/PREDICTION_ENGINE_SPEC.md`](docs/PREDICTION_ENGINE_SPEC.md). The first pure pricing/ranking utilities are in `tools/prediction.py`, with unit tests in `tests/test_prediction.py`. The experimental Poisson baseline now uses league goal baselines and home/away team scoring and conceding rates when available, with a shrunk recent-form fallback. A separate in-play model estimates goals remaining from match time, score, live shots and red cards. A chronological walk-forward backtest reports probability metrics without inventing ROI when historical odds are unavailable. The MCP tool `predict_match_bet(fixture_id)` selects a primary pre-match candidate, compares supported markets with the best prices returned across available bookmakers, and keeps all candidates visible. The model is not calibrated or backtested: positive point-estimate EV is capped at LEAN, and VALUE_BET remains disabled until validation. See `docs/RECOMMENDATION_TOOL.md` and `docs/BACKTESTING_AND_LIVE.md`.
