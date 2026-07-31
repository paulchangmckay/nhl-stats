# Turso + Render Deploy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the NHL Stats app's database from a local 1.48GB SQLite file to Turso (hosted libSQL), and deploy the Flask app + built frontend to Render's free tier, auto-deploying on every push to `main`.

**Architecture:** `src/database.py`'s `get_connection()` gains a second backend, selected by the presence of `TURSO_DATABASE_URL`: local `sqlite3` (unchanged, used for dev/tests) or a new `libsql`-backed connection wrapped in a thin `sqlite3.Row`-compatible adapter (required — see Global Constraints). The app is containerized (multi-stage Dockerfile: Node build stage for the frontend, Python/gunicorn runtime stage) and deployed via Render's native GitHub integration. Data migrates from the local file into Turso via a direct file import, then local ETL runs are repointed at Turso.

**Tech Stack:** Python 3.12, Flask, `libsql` 0.1.11, gunicorn 26.0.0, Node 22 (frontend build only), Docker, Render, Turso CLI.

## Global Constraints

- `libsql` has no prebuilt wheel for Python 3.14 as of this writing (confirmed: install fails on 3.14, succeeds on 3.12). This project's `.venv` currently runs 3.14, but CI (`.github/workflows/ci.yml`) already targets 3.12. **All work in this plan must run under Python 3.12**, not the existing `.venv`. Task 1 Step 1 sets this up.
- `libsql`'s `Connection` object has **no `row_factory` attribute** (confirmed by direct testing — assigning one raises `AttributeError`). Query results come back as plain tuples. Since `row["column_name"]` access is used throughout `app.py`, `src/database.py`, and the test suite, every Turso-backed connection MUST go through the `_TursoConnection`/`_TursoRow` adapter built in Task 1 — never call `libsql.connect()` directly anywhere else in the codebase.
- Duplicate `ALTER TABLE ... ADD COLUMN` against `libsql` raises `ValueError` (confirmed by direct testing), not `sqlite3.OperationalError`. Task 3 depends on this.
- Turso's `db create --from-file` import path has a 2GB file size limit. The current DB (1.48GB) fits; if it grows past 2GB before Task 7 runs, the import step needs a different approach (out of scope — flagged here so it isn't missed).
- No changes to local-only dev/test behavior: with `TURSO_DATABASE_URL` unset, `get_connection()` must behave exactly as it does today (verified by the existing test suite passing unchanged).
- Don't touch query logic in `app.py`/`etl/*.py`/`scripts/*.py` — the adapter is designed so none of it needs to change.

---

### Task 1: `libsql` row-adapter (`_TursoConnection`/`_TursoCursor`/`_TursoRow`)

**Files:**
- Modify: `requirements.txt` (add `libsql==0.1.11`)
- Modify: `src/database.py` (add adapter classes near the top, before `get_connection`)
- Test: `tests/test_database_libsql_adapter.py` (new)

**Interfaces:**
- Produces: `_TursoConnection(raw_libsql_connection)` — exposes `.execute(sql, params=())`, `.executemany(sql, seq_of_params)`, `.commit()`, `.close()`. `.execute()` returns a `_TursoCursor` whose `.fetchone()`/`.fetchall()` return `_TursoRow` objects supporting `row["col"]`, `row[0]`, `row.keys()`, and iteration — matching `sqlite3.Row`'s interface as used elsewhere in this codebase.

- [ ] **Step 1: Set up a Python 3.12 environment for this work**

The project's existing `.venv` is Python 3.14, which `libsql` cannot install into. Create a separate 3.12 venv for this plan's work (CI already uses 3.12, so this also matches what actually runs in GitHub Actions):

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
/opt/homebrew/bin/python3.12 -m venv .venv312
./.venv312/bin/pip install -r requirements.txt -r requirements-dev.txt
```

Expected: installs cleanly, no wheel-build errors. Use `./.venv312/bin/python` / `./.venv312/bin/pytest` for every command in this plan from here on.

- [ ] **Step 2: Add the `libsql` dependency**

Edit `requirements.txt` to add one line:

```
libsql==0.1.11
```

Reinstall: `./.venv312/bin/pip install -r requirements.txt`

- [ ] **Step 3: Write the failing test**

Create `tests/test_database_libsql_adapter.py`:

```python
import libsql
import pytest

from src.database import _TursoConnection


def _wrapped_conn(tmp_path, name):
    raw = libsql.connect(str(tmp_path / name))
    return _TursoConnection(raw)


def test_fetchone_supports_dict_style_column_access(tmp_path):
    conn = _wrapped_conn(tmp_path, "adapter_test1.db")
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO t (id, name) VALUES (?, ?)", (1, "alice"))
    conn.commit()

    row = conn.execute("SELECT * FROM t WHERE id = ?", (1,)).fetchone()

    assert row["id"] == 1
    assert row["name"] == "alice"


def test_fetchall_returns_dict_style_rows_in_order(tmp_path):
    conn = _wrapped_conn(tmp_path, "adapter_test2.db")
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO t (id, name) VALUES (?, ?)", (1, "alice"))
    conn.execute("INSERT INTO t (id, name) VALUES (?, ?)", (2, "bob"))
    conn.commit()

    rows = conn.execute("SELECT * FROM t ORDER BY id").fetchall()

    assert [r["name"] for r in rows] == ["alice", "bob"]


def test_fetchone_returns_none_when_no_row_matches(tmp_path):
    conn = _wrapped_conn(tmp_path, "adapter_test3.db")
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
    conn.commit()

    assert conn.execute("SELECT * FROM t WHERE id = ?", (99,)).fetchone() is None


def test_row_supports_integer_indexing_and_keys(tmp_path):
    conn = _wrapped_conn(tmp_path, "adapter_test4.db")
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO t (id, name) VALUES (?, ?)", (1, "alice"))
    conn.commit()

    row = conn.execute("SELECT * FROM t WHERE id = ?", (1,)).fetchone()

    assert row[0] == 1
    assert row[1] == "alice"
    assert list(row.keys()) == ["id", "name"]


def test_on_conflict_upsert_and_row_access_together(tmp_path):
    conn = _wrapped_conn(tmp_path, "adapter_test5.db")
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO t (id, name) VALUES (?, ?)", (1, "alice"))
    conn.commit()

    conn.execute(
        "INSERT INTO t (id, name) VALUES (?, ?) "
        "ON CONFLICT(id) DO UPDATE SET name = excluded.name",
        (1, "alice-updated"),
    )
    conn.commit()

    row = conn.execute("SELECT name FROM t WHERE id = ?", (1,)).fetchone()
    assert row["name"] == "alice-updated"
```

- [ ] **Step 4: Run the tests to verify they fail**

```bash
./.venv312/bin/pytest tests/test_database_libsql_adapter.py -v
```

Expected: FAIL with `ImportError: cannot import name '_TursoConnection' from 'src.database'` (the class doesn't exist yet).

- [ ] **Step 5: Implement the adapter**

In `src/database.py`, add after the existing imports (`import sqlite3` / `import os`) and before `DB_PATH`:

```python
class _TursoRow:
    """sqlite3.Row-compatible wrapper around a libsql result tuple."""

    __slots__ = ("_columns", "_values")

    def __init__(self, columns, values):
        self._columns = columns
        self._values = values

    def __getitem__(self, key):
        if isinstance(key, str):
            return self._values[self._columns.index(key)]
        return self._values[key]

    def keys(self):
        return list(self._columns)

    def __iter__(self):
        return iter(self._values)

    def __repr__(self):
        return f"<_TursoRow {dict(zip(self._columns, self._values))}>"


class _TursoCursor:
    """Wraps a libsql cursor so fetchone/fetchall return _TursoRow objects."""

    def __init__(self, cursor):
        self._cursor = cursor

    def _columns(self):
        return [d[0] for d in self._cursor.description]

    def fetchone(self):
        row = self._cursor.fetchone()
        return _TursoRow(self._columns(), row) if row is not None else None

    def fetchall(self):
        columns = self._columns()
        return [_TursoRow(columns, row) for row in self._cursor.fetchall()]

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class _TursoConnection:
    """Wraps a libsql connection so conn.execute(...).fetchone()/.fetchall()
    return sqlite3.Row-compatible objects, matching the interface every
    caller in this codebase already relies on."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=()):
        return _TursoCursor(self._conn.execute(sql, params))

    def executemany(self, sql, seq_of_params):
        return self._conn.executemany(sql, seq_of_params)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()
```

- [ ] **Step 6: Run the tests to verify they pass**

```bash
./.venv312/bin/pytest tests/test_database_libsql_adapter.py -v
```

Expected: 5 passed.

- [ ] **Step 7: Run the full existing test suite to confirm no regression**

```bash
./.venv312/bin/pytest tests/ -v
```

Expected: all existing tests still pass (this task only adds new classes; nothing existing imports or calls them yet).

- [ ] **Step 8: Commit**

```bash
git add requirements.txt src/database.py tests/test_database_libsql_adapter.py
git commit -m "Add libsql row-adapter for Turso-compatible dict-style row access"
```

---

### Task 2: `get_connection()` backend selection

**Files:**
- Modify: `src/database.py:449-454` (the existing `get_connection` function)
- Test: `tests/test_database_get_connection.py` (new)

**Interfaces:**
- Consumes: `_TursoConnection` from Task 1 (`src/database.py`).
- Produces: `get_connection(db_path=DB_PATH)` — same signature and default as today. When `TURSO_DATABASE_URL` env var is set, returns a `_TursoConnection` wrapping a `libsql.connect(database=..., auth_token=...)` connection instead of a local `sqlite3.Connection`. `db_path` argument is ignored in that case (kept for backward-compatible signature/tests).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_database_get_connection.py`:

```python
import sys
import types

import pytest

from src import database


def test_get_connection_uses_sqlite_when_turso_url_not_set(tmp_path, monkeypatch):
    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)

    conn = database.get_connection(db_path=str(tmp_path / "local.db"))

    import sqlite3
    assert isinstance(conn, sqlite3.Connection)
    conn.close()


def test_get_connection_uses_libsql_when_turso_url_set(monkeypatch):
    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://example-org.turso.io")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "fake-token")

    calls = {}

    class _FakeRawConn:
        def execute(self, sql, params=()):
            calls.setdefault("executed", []).append(sql)
            class _FakeCursor:
                description = ()
                def fetchone(self):
                    return None
                def fetchall(self):
                    return []
            return _FakeCursor()
        def commit(self):
            pass
        def close(self):
            pass

    fake_libsql = types.SimpleNamespace(
        connect=lambda database, auth_token: (
            calls.__setitem__("connect_args", {"database": database, "auth_token": auth_token})
            or _FakeRawConn()
        )
    )
    monkeypatch.setitem(sys.modules, "libsql", fake_libsql)

    conn = database.get_connection()

    assert isinstance(conn, database._TursoConnection)
    assert calls["connect_args"] == {
        "database": "libsql://example-org.turso.io",
        "auth_token": "fake-token",
    }
```

- [ ] **Step 2: Run to verify failure**

```bash
./.venv312/bin/pytest tests/test_database_get_connection.py -v
```

Expected: `test_get_connection_uses_libsql_when_turso_url_set` FAILs (still returns a plain `sqlite3.Connection` since the branch doesn't exist yet); the sqlite test passes already (no regression risk there).

- [ ] **Step 3: Implement the branch**

Replace `get_connection` in `src/database.py`:

```python
def get_connection(db_path=DB_PATH):
    turso_url = os.environ.get("TURSO_DATABASE_URL")
    if turso_url:
        import libsql
        raw = libsql.connect(database=turso_url, auth_token=os.environ["TURSO_AUTH_TOKEN"])
        conn = _TursoConnection(raw)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
```

The `import libsql` stays inside the branch (not a module-level import) so local dev/test work that never sets `TURSO_DATABASE_URL` never requires `libsql` to be installed or importable.

- [ ] **Step 4: Run to verify both tests pass**

```bash
./.venv312/bin/pytest tests/test_database_get_connection.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Run the full suite**

```bash
./.venv312/bin/pytest tests/ -v
```

Expected: all pass, including `tests/conftest.py`'s `conn` fixture (which calls `get_connection` with no `TURSO_DATABASE_URL` set in CI/local dev, so it takes the unchanged sqlite path).

- [ ] **Step 6: Commit**

```bash
git add src/database.py tests/test_database_get_connection.py
git commit -m "Branch get_connection() on TURSO_DATABASE_URL to support Turso backend"
```

---

### Task 3: Migration idempotency against libsql

**Files:**
- Modify: `src/database.py:457-463` (`run_migrations`)
- Test: `tests/test_database_migrations_libsql.py` (new)

**Interfaces:**
- Consumes: `_TursoConnection` (Task 1), `run_migrations(conn)` (existing).

- [ ] **Step 1: Write the failing test**

Create `tests/test_database_migrations_libsql.py`:

```python
import libsql

from src.database import _TursoConnection, run_migrations


def test_run_migrations_is_idempotent_against_libsql_backend(tmp_path):
    raw = libsql.connect(str(tmp_path / "migrations_test.db"))
    conn = _TursoConnection(raw)
    # Minimal subset of a real migration target column, enough to exercise
    # the duplicate-ADD-COLUMN path without needing the full schema.
    conn.execute("CREATE TABLE players (player_id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.execute("ALTER TABLE players ADD COLUMN position_code TEXT")
    conn.commit()

    # Running migrations again (which will try to re-add position_code,
    # among others) must not raise.
    run_migrations(conn)
```

- [ ] **Step 2: Run to verify it fails**

```bash
./.venv312/bin/pytest tests/test_database_migrations_libsql.py -v
```

Expected: FAIL with `ValueError: duplicate column name: position_code` (uncaught, since `run_migrations` only catches `sqlite3.OperationalError` today).

- [ ] **Step 3: Fix the exception handling**

In `src/database.py`, update `run_migrations`:

```python
def run_migrations(conn):
    for sql in _PLAYER_MIGRATIONS + _GAME_EVENTS_MIGRATIONS + _ADVANCED_STATS_MIGRATIONS:
        try:
            conn.execute(sql)
        except (sqlite3.OperationalError, ValueError):
            pass  # column already exists (sqlite3.OperationalError locally, ValueError via libsql)
    conn.commit()
```

- [ ] **Step 4: Run to verify it passes**

```bash
./.venv312/bin/pytest tests/test_database_migrations_libsql.py -v
```

Expected: PASS.

- [ ] **Step 5: Run the full suite**

```bash
./.venv312/bin/pytest tests/ -v
```

Expected: all pass (the local-sqlite migration path is unaffected — `sqlite3.OperationalError` is still caught, `ValueError` is just an additional caught type that sqlite3 never raises for this case).

- [ ] **Step 6: Commit**

```bash
git add src/database.py tests/test_database_migrations_libsql.py
git commit -m "Make run_migrations idempotent against libsql's ValueError on duplicate columns"
```

---

### Task 4: Configurable host/port for Docker

**Files:**
- Modify: `app.py` (bottom, `_debug_enabled` / `__main__` block)
- Test: `tests/test_app_helpers.py` (existing file, add tests)

**Interfaces:**
- Produces: `_host_port()` in `app.py` — returns `(host: str, port: int)`, reading `HOST` (default `"127.0.0.1"`) and `PORT` (default `5099`) from the environment.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_app_helpers.py` (alongside the existing `_toi_str`/`_height_str`/`_debug_enabled` tests, same import line updated):

```python
from app import _toi_str, _height_str, _debug_enabled, _fetch_players, _host_port
```

```python
def test_host_port_defaults_to_localhost_5099(monkeypatch):
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.delenv("PORT", raising=False)

    assert _host_port() == ("127.0.0.1", 5099)


def test_host_port_reads_env_overrides(monkeypatch):
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.setenv("PORT", "7860")

    assert _host_port() == ("0.0.0.0", 7860)
```

- [ ] **Step 2: Run to verify failure**

```bash
./.venv312/bin/pytest tests/test_app_helpers.py -v
```

Expected: FAIL with `ImportError: cannot import name '_host_port' from 'app'`.

- [ ] **Step 3: Implement**

In `app.py`, replace the bottom `__main__` block:

```python
def _debug_enabled():
    return os.environ.get("FLASK_DEBUG") == "1"


def _host_port():
    return os.environ.get("HOST", "127.0.0.1"), int(os.environ.get("PORT", "5099"))


if __name__ == "__main__":
    host, port = _host_port()
    app.run(debug=_debug_enabled(), host=host, port=port)
```

- [ ] **Step 4: Run to verify it passes**

```bash
./.venv312/bin/pytest tests/test_app_helpers.py -v
```

Expected: PASS (all tests in the file, including the pre-existing ones).

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_app_helpers.py
git commit -m "Make Flask host/port configurable via env vars for container deploys"
```

---

### Task 5: Fix stale `sqlite3` CLI example in `scripts/sync.py`

**Files:**
- Modify: `scripts/sync.py` (docstring only)

**Interfaces:** none (documentation-only change, no behavior).

- [ ] **Step 1: Edit the docstring**

Find the line in `scripts/sync.py`'s module docstring containing the literal example:
```
sqlite3 data/nhl_stats.db "DELETE FROM sync_log ..."
```
Replace it with a note reflecting the dual-backend reality, e.g.:
```
# Local dev DB: sqlite3 data/nhl_stats.db "DELETE FROM sync_log ..."
# Production (Turso): requires TURSO_DATABASE_URL/TURSO_AUTH_TOKEN to be set;
# use `turso db shell <db-name>` for ad-hoc queries instead of the sqlite3 CLI.
```

- [ ] **Step 2: Confirm no test references this docstring text**

```bash
grep -rn "DELETE FROM sync_log" tests/
```

Expected: no matches (it's documentation, not asserted-on behavior).

- [ ] **Step 3: Commit**

```bash
git add scripts/sync.py
git commit -m "Update sync.py's stale sqlite3-only CLI example for the Turso backend"
```

---

### Task 6: Dockerfile, `.dockerignore`, gunicorn

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Modify: `requirements.txt` (add `gunicorn==26.0.0`)

**Interfaces:** none (infrastructure files, no Python interface).

- [ ] **Step 1: Add gunicorn**

Edit `requirements.txt`, add:
```
gunicorn==26.0.0
```

- [ ] **Step 2: Create `.dockerignore`**

```
.git
.github
.venv
.venv312
venv
__pycache__
*.pyc
.pytest_cache
.wolf
.worktrees
.superpowers
.run
.claude
.claudeignore
data
files
files.zip
docs
tests
frontend/node_modules
frontend/dist
static/dist
README.md
CONTRIBUTING.md
requirements-dev.txt
```

- [ ] **Step 3: Create `Dockerfile`**

```dockerfile
# Stage 1: build the frontend
FROM node:22-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: run the Flask app
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY src/ ./src/
COPY templates/ ./templates/
COPY --from=frontend-build /app/static/dist ./static/dist
ENV PORT=7860
EXPOSE 7860
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --workers 2 app:app"]
```

(`frontend/vite.config.ts`'s `outDir: "../static/dist"` means the frontend build stage, run from `/app/frontend`, writes its output to `/app/static/dist` — the `COPY --from=frontend-build` path matches that.)

- [ ] **Step 4: Build the image locally**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
docker build -t nhl-stats-test .
```

Expected: build completes successfully through both stages, ending with the image tagged `nhl-stats-test`.

- [ ] **Step 5: Run the image and verify it serves traffic**

```bash
docker run --rm -p 7860:7860 -e HOST=0.0.0.0 -e PORT=7860 nhl-stats-test &
sleep 3
curl -sf http://127.0.0.1:7860/ -o /dev/null -w "%{http_code}\n"
```

Expected: `200`. Then stop the container:

```bash
docker stop $(docker ps -q --filter ancestor=nhl-stats-test)
```

Note: without `TURSO_DATABASE_URL` set, any route hitting `get_connection()` falls back to a local sqlite path (`data/nhl_stats.db`) that doesn't exist inside the image (it's `.dockerignore`d) — the `/` route itself (`render_template("index.html")`) doesn't touch the DB, so this smoke test only proves the container serves HTTP traffic and the frontend build landed correctly. Full API verification happens in Task 8 once `TURSO_DATABASE_URL` is set against the real deployed environment.

- [ ] **Step 6: Commit**

```bash
git add Dockerfile .dockerignore requirements.txt
git commit -m "Add multi-stage Dockerfile (frontend build + gunicorn) for container deploys"
```

---

### Task 7: Provision Turso and migrate data (manual/infra)

**Files:** none (external service provisioning + one-time data migration; no repo changes except the env var note added to Task 8).

**Interfaces:** produces the `TURSO_DATABASE_URL` / `TURSO_AUTH_TOKEN` values Task 2 and Task 8 consume.

- [ ] **Step 1: Install the Turso CLI and log in**

```bash
curl -sSfL https://get.tur.so/install.sh | bash
turso auth login
```

- [ ] **Step 2: Run a final local ETL sync**

Ensures `data/nhl_stats.db` is fully up to date before it becomes the import source (per the spec's cutover ordering):

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
./.venv312/bin/python scripts/sync.py
```

Expected: completes without error (this project's existing incremental sync — not the multi-hour historical backfill).

- [ ] **Step 3: Import the local file into a new Turso database**

```bash
turso db create nhl-stats --from-file data/nhl_stats.db
```

Expected: succeeds (file is 1.48GB, under the 2GB import limit). Note the database name `nhl-stats` for the next steps.

- [ ] **Step 4: Get the connection URL and create an auth token**

```bash
turso db show nhl-stats --url
turso db tokens create nhl-stats
```

Save both values — they become `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN`.

- [ ] **Step 5: Verify row counts match between the local file and Turso**

```bash
sqlite3 data/nhl_stats.db "SELECT 'game_events', COUNT(*) FROM game_events UNION ALL SELECT 'player_shifts', COUNT(*) FROM player_shifts UNION ALL SELECT 'player_game_stats', COUNT(*) FROM player_game_stats;"
turso db shell nhl-stats "SELECT 'game_events', COUNT(*) FROM game_events UNION ALL SELECT 'player_shifts', COUNT(*) FROM player_shifts UNION ALL SELECT 'player_game_stats', COUNT(*) FROM player_game_stats;"
```

Expected: the three counts from each command match exactly.

- [ ] **Step 6: Point local ETL at Turso going forward**

Only after Step 5's verification passes. Add to your shell profile or a local (gitignored) `.env`-style export — not committed to the repo:

```bash
export TURSO_DATABASE_URL="<url from step 4>"
export TURSO_AUTH_TOKEN="<token from step 4>"
```

From this point, running `scripts/run_all_etl.py` / `scripts/sync.py` locally with these variables set writes to Turso, not to `data/nhl_stats.db`. The local file remains only for dev/test use (Task 1-3's tests, `tests/conftest.py`'s fixture) — stop treating it as a production data source.

- [ ] **Step 7: Confirm ETL against Turso works end-to-end**

```bash
./.venv312/bin/python scripts/sync.py
```

Expected: completes without error, now writing through the `_TursoConnection` path built in Tasks 1-3.

---

### Task 8: Deploy to Render (manual/infra)

**Files:** none (external service configuration).

**Interfaces:** consumes the Dockerfile (Task 6) and `TURSO_DATABASE_URL`/`TURSO_AUTH_TOKEN` (Task 7).

- [ ] **Step 1: Push all committed work from Tasks 1-6 to GitHub**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git push origin main
```

- [ ] **Step 2: Create the Render service**

In the Render dashboard: New → Web Service → connect the `paulchangmckay/nhl-stats` GitHub repo → Environment: **Docker** (Render auto-detects the root `Dockerfile`) → Instance Type: **Free**.

- [ ] **Step 3: Set environment secrets**

In the new service's Environment settings, add:
- `TURSO_DATABASE_URL` = the URL from Task 7 Step 4
- `TURSO_AUTH_TOKEN` = the token from Task 7 Step 4

Do not set `PORT` — Render supplies it automatically and the Dockerfile's `ENV PORT=7860` is only a fallback default for local `docker run`.

- [ ] **Step 4: Deploy and verify**

Trigger the first deploy (automatic on service creation). Once it reports "Live", verify both a static route and a DB-backed API route against the Render-provided `*.onrender.com` URL:

```bash
curl -sf https://<your-service>.onrender.com/ -o /dev/null -w "%{http_code}\n"
curl -sf https://<your-service>.onrender.com/api/teams -o /dev/null -w "%{http_code}\n"
```

Expected: both `200`. The second call is the real end-to-end proof that the deployed container reaches Turso successfully through the full `get_connection()` → `_TursoConnection` → `libsql` path built in Tasks 1-3.

- [ ] **Step 5: Confirm auto-deploy on push**

Make any trivial commit to `main` (e.g. a README typo fix) and push. Expected: Render starts a new deploy automatically within a few seconds, with no manual trigger needed — confirming the native GitHub integration is wired up as intended.

---

## Self-Review Notes

- **Spec coverage:** Section 1 (DB layer + row adapter) → Tasks 1-3. Section 2 (data migration, exact cutover sequence) → Task 7. Section 3 (Dockerfile, Render, secrets) → Tasks 6, 8. Section 4 (testing/CI scope decisions) → reflected in Tasks 1-3's tests staying local/mock-based, no new CI job added. The "future schema changes are manual, run against Turso" decision from grilling → covered implicitly by Task 7's pattern (Task 3 makes `run_migrations` Turso-safe; running it against Turso is a manual `scripts/setup_db.py` invocation with `TURSO_DATABASE_URL` set, same pattern as Task 7 Step 7's ETL run — no separate task needed since the mechanism is identical to what Task 7 already exercises).
- **No placeholders:** every step has real code or exact commands with expected output.
- **Type/interface consistency checked:** `_TursoConnection`/`_TursoCursor`/`_TursoRow` names and method signatures are identical across Tasks 1, 2, and 3. `_host_port()` return type `(str, int)` used consistently in Task 4.
