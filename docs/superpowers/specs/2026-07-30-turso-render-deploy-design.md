# Design: Migrate to Turso + Deploy to Render

Date: 2026-07-30

## Problem

The NHL Stats app (Flask backend + Vite/React frontend, `app.py` serving both) currently
runs only against a local SQLite file (`data/nhl_stats.db`, 1.48GB, gitignored, never
deployed). The goal is to get this app deployed and auto-updating from GitHub, with the
database persisted somewhere that survives redeploys/restarts.

Constraints discovered during exploration/discussion:
- The DB is too large for git (1.48GB, gitignored) and for most free managed-Postgres
  tiers (Neon 0.5GB, Supabase 500MB free).
- Cloudflare Workers (the platform originally targeted) cannot run Flask: Python Workers
  are beta and deployed Workers may only use the standard library — third-party packages
  including Flask only work in local dev, not production. Ruled out as an app host.
- Hugging Face Docker Spaces were the next candidate, but Docker Spaces now require HF
  Pro ($9/month) for personal accounts (a recent, undocumented platform change) — ruled
  out in favor of a genuinely free option.
- `src/database.py` uses no SQLite-specific features that would block a libSQL-compatible
  backend: no `ATTACH`, no BLOBs, no FTS, no custom SQLite functions. It does use
  `sqlite3.Row` row factory, `?` placeholders, `INSERT OR REPLACE`/`INSERT OR IGNORE`,
  `ON CONFLICT ... DO UPDATE ... excluded.*`, `datetime('now')`, and a migration loop that
  catches `sqlite3.OperationalError` for idempotent `ALTER TABLE ADD COLUMN` statements.
- All DB access goes through `get_connection()` in `src/database.py` — no other file
  imports `sqlite3` directly. Flask (`app.py`) opens one connection per request. ETL
  scripts (`etl/*.py`) each take a long-lived connection via `run(conn)`, committing
  per-row or per-game (no batching/`executemany`).
- Tests (`tests/conftest.py`) use a real file-backed SQLite DB via `tmp_path`, not
  `:memory:`, and monkeypatch `get_connection` by name.
- No existing `Dockerfile`. `static/dist/` (the built frontend) is gitignored — nothing
  commits a production frontend build today. `app.py` binds to `127.0.0.1:5099` by
  default; no host/port env override exists yet. Only env var currently in use is
  `FLASK_DEBUG`. No API keys — the NHL API is public/unauthenticated.
- Existing CI (`.github/workflows/ci.yml`) runs tests only on PRs to `main`, not on push,
  and has no deploy/Docker step.

## Chosen architecture

```
GitHub (paulchangmckay/nhl-stats, push to main)
        |
        +-- ci.yml (tests, PR-triggered) -- unchanged
        +-- Render (native GitHub auto-deploy on push to main)
                        |
                        v
        Render free tier (Docker) -- runs Flask app + built frontend
                        |
                        v  (remote libSQL connection)
        Turso -- hosted database (migrated from data/nhl_stats.db)

ETL scripts -- still run locally on the developer's machine, now writing
               to Turso directly instead of the local sqlite file.
```

No Cloudflare component. The Cloudflare Worker `nhl-stats.paulchangmckay.workers.dev`
that prompted this work is retired from the design: Python Workers can't deploy Flask
(stdlib-only in production), and once the app has a public Render URL there's no
remaining role for it as a proxy.

Connection mode to Turso: **remote-only** (no embedded replica). Every query is a
network round trip to Turso. Chosen over an embedded local-replica-with-sync setup for
simplicity — no sync lifecycle to manage, no local disk to provision, no cold-start
resync after Render's free tier spins the service down on idle. Acceptable given this is
a low-traffic personal dashboard; per-request latency is a reasonable tradeoff for the
reduction in moving parts.

## 1. Database layer (`src/database.py`)

`get_connection()` branches on an environment variable:

- **`TURSO_DATABASE_URL` is set** (production/Render): connect via the official `libsql`
  Python package (DB-API-2.0-compatible, sqlite3-like interface) to the remote Turso
  database, authenticating with `TURSO_AUTH_TOKEN`.
- **Not set** (local dev, tests, CI): unchanged — `sqlite3.connect()` against a local
  file, exactly as today.

Rationale: one additional dependency (`libsql`), but the local-dev/test path keeps using
stdlib `sqlite3` untouched, so `tests/conftest.py`'s file-backed fixture and the
`get_connection`-monkeypatching in `tests/test_app_advanced_stats.py` need no changes.
CI does not need Turso credentials.

Existing query code (`app.py`, `etl/*.py`, `scripts/*.py`) needs no SQL changes — the
`sqlite3.Row`-style dict access and `?` placeholders both work unchanged against libSQL.

One required code change: the migration loop in `run_migrations()` currently does
`except sqlite3.OperationalError: pass` to make repeated `ALTER TABLE ADD COLUMN`
idempotent. This must also catch libSQL's equivalent "duplicate column" error type when
running against a Turso connection, or migrations will crash on second run against Turso.

**Future schema changes:** `app.py` never calls `create_all_tables()`/`run_migrations()`
itself — only `scripts/setup_db.py` does, and only when run manually. This stays true
after the Turso migration: applying a future schema change to production means manually
running `scripts/setup_db.py` with `TURSO_DATABASE_URL`/`TURSO_AUTH_TOKEN` set, as a
deliberate step you run yourself. Render and CI never run it automatically — this avoids
two Render instances racing to `ALTER TABLE` against the same remote DB on a cold start,
and keeps the existing manual-migration pattern unchanged.

**Connection lifecycle:** stays per-request connect/close, exactly as today — `app.py`
opens a fresh connection per request and closes it. Against remote Turso this means each
request pays a full connection-establishment cost (not just one query round trip), but a
persistent/pooled connection reused across requests is deliberately out of scope for the
first version: it adds thread-safety and reconnect-on-drop concerns under gunicorn worker
processes that aren't worth taking on before knowing whether latency is actually a
problem for a low-traffic personal dashboard. Revisit only if real usage shows it matters.

`scripts/sync.py`'s docstring contains a literal `sqlite3 data/nhl_stats.db "DELETE
FROM sync_log ..."` CLI example; update it to reflect the new dual-backend reality (or
note it's dev-only guidance) so it doesn't mislead future readers.

## 2. Data migration (one-time)

Exact cutover sequence, to avoid a window where local-file and Turso data diverge:

1. Run a final local ETL sync so `data/nhl_stats.db` is fully up to date.
2. Import that exact file into a new Turso database via Turso's CLI import-from-file
   capability — libSQL reads native SQLite file format, so this is a direct file import,
   not a custom export/transform script.
3. Verify row counts per table between the local file and Turso match (spot-check the
   largest tables: `game_events`, `player_shifts`, `player_game_stats`).
4. Only after verification passes, set `TURSO_DATABASE_URL`/`TURSO_AUTH_TOKEN` in the
   local ETL environment so all subsequent ETL runs write to Turso. From this point the
   local file is no longer a write target for real data — it remains dev/test-only.

Running ETL against the local file for any period *after* the Turso import would let the
two silently diverge, so step 4 happens immediately after step 3 passes, not on a delay.

## 3. Deployment (Render)

- New multi-stage `Dockerfile`:
  - **Stage 1** (node): `npm ci && npm run build` inside `frontend/`, producing
    `static/dist` (currently gitignored and never committed — the Dockerfile is what
    produces it for deployment).
  - **Stage 2** (python): install `requirements.txt` (+ `libsql`), copy application code
    and the built `static/dist` from stage 1, run via `gunicorn` (replacing the Flask dev
    server for production), binding to `0.0.0.0` on the port Render provides via `$PORT`
    (`app.py`'s current hardcoded `port=5099`/implicit `127.0.0.1` host needs to become
    configurable).
- Render service connected directly to the `paulchangmckay/nhl-stats` GitHub repo, with
  Render's native auto-deploy-on-push to `main` — no custom GitHub Actions workflow
  needed for deployment.
- `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` set as Render environment secrets (never
  committed to the repo).
- Public URL is Render's provided `*.onrender.com` URL (or a custom domain later, out of
  scope for this design).

## 4. Testing / CI

`.github/workflows/ci.yml` is unchanged — tests continue to run against a local,
file-backed sqlite DB with no Turso credentials required in CI. No new CI job is needed
since Render's GitHub integration handles deploy natively. This means the `libsql`/Turso
branch of `get_connection()` is never exercised by automated tests — accepted, since it's
a small (~10 line) connection-opening branch, verified once by the spike below and once
by an actual pre-deploy run against real Turso, while all query logic in `app.py`/`etl/*`
stays fully covered by the existing local-sqlite test suite regardless of which backend
runs it.

`ci.yml` also still triggers on PRs only, not on push to `main`; Render's auto-deploy
triggers on every push to `main` with no test gate of its own. Accepted as-is — PRs
already gate merges to `main` in the normal flow for this solo project, and wiring a
required-status-check between GitHub Actions and Render's deploy trigger isn't worth the
added pipeline complexity to guard against an accidental direct push.

## Implementation ordering note

The claim that existing query code needs zero changes against `libsql` rests on
assumptions about that package's API (sqlite3.Row-style dict row access, `?`
placeholders, `INSERT OR REPLACE`/`ON CONFLICT...excluded.*` support, and a catchable
duplicate-column error equivalent to `sqlite3.OperationalError`). The implementation plan
must start with a small spike — connect to a throwaway Turso test database via `libsql`,
run one insert/upsert/read round trip and one intentionally-duplicate `ALTER TABLE ADD
COLUMN` — to confirm these before writing any other migration code.

## Out of scope

- Embedded-replica / local-sync mode for Turso (may revisit if remote-only latency proves
  a problem in practice).
- Running ETL from inside the deployed service (stays a local/manual developer task).
- Custom domain / any Cloudflare component.
- Upgrading Render beyond the free tier (accepting sleep-on-idle/cold-start behavior for
  now).
