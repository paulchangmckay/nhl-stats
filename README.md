# NHL Stats Database

A learning project for building a local NHL stats database using the NHL's free public API and SQLite.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the branching workflow used in this repo.

## What this project teaches
- **Git** — branching, commits, pull requests
- **REST APIs** — fetching JSON data with Python `requests`
- **SQLite** — schema design, INSERT/UPDATE, JOINs, aggregation
- **ETL pipelines** — Extract, Transform, Load patterns

## Data Source
NHL Web API — `https://api-web.nhle.com/v1/` (free, no auth required)

## Setup

```bash
# 1. Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create the database and all tables
python scripts/setup_db.py

# 4. Run all ETL to populate the database
python scripts/run_all_etl.py

# 5. Try the example queries
python scripts/query_examples.py
```

## Database Schema

| Table | Description |
|---|---|
| `teams` | All 32 NHL teams |
| `seasons` | NHL season identifiers |
| `players` | Player roster data |
| `games` | Game schedule and scores |
| `player_game_stats` | Per-player per-game stats |
| `standings` | Daily standings snapshots |

## Project Structure

```
src/          — Core modules (API client, DB helpers, models)
etl/          — One script per data type (teams, players, games, etc.)
scripts/      — Runnable entry points (setup, ETL runner, query examples)
data/         — SQLite database file (git-ignored)
```
