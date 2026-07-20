# NHL Stats Database

Last updated: 2026-07-12 11:37 PM CDT

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

### One-time historical backfill (play-by-play & shifts)

`run_all_etl.py` keeps `game_events` and `player_shifts` current for new
games automatically. The *first* time you populate these tables, though,
there are ~7,800+ historical games (6 seasons, regular season + playoffs)
to backfill — realistically hours, not the seconds `run_all_etl.py`'s other
steps take. Run this once, standalone, before your first `run_all_etl.py`
run against a fresh database:

```bash
python -m etl.load_historical_schedule
python -m etl.load_boxscores
python -m etl.load_play_by_play
python -m etl.load_shifts
```

Each script is idempotent and resumable (safe to re-run or interrupt
partway through — already-loaded games are skipped). After this completes
once, `python scripts/run_all_etl.py` is sufficient going forward; the
same three steps run as fast no-ops when there's nothing new to load.

### Frontend (React + Vite)

Install once:
```bash
cd frontend && npm install
```

Run both the Flask API and the Vite dev server with one command:
```bash
./scripts/dev.sh
```
This starts Flask on `http://127.0.0.1:5099` and the Vite dev server on
`http://localhost:5173` (which proxies `/api/*` to Flask). Ctrl+C stops both.

## Testing & local checks

```bash
# Install dev dependencies (adds pytest, bandit, pip-audit on top of requirements.txt)
pip install -r requirements-dev.txt

# Run the test suite
python -m pytest tests/ -v

# Run the JS unit tests (search/autocomplete matching logic)
node --test tests/js/search.test.js

# Run the dependency-audit + SAST gate (same script CI runs)
./scripts/audit.sh
```

By default the Flask dev server runs with the debugger off. Set `FLASK_DEBUG=1`
before `python app.py` to enable it locally — never in a deployed environment.

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
scripts/      — Runnable entry points (setup, ETL runner, query examples, audit.sh)
tests/        — pytest suite (pure-logic helpers + database upsert regression tests)
data/         — SQLite database file (git-ignored)
```
