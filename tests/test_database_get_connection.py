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
