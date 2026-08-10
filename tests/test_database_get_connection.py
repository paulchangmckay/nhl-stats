import pytest

from src import database


def test_get_connection_uses_sqlite_when_turso_url_not_set(tmp_path, monkeypatch):
    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)

    conn = database.get_connection(db_path=str(tmp_path / "local.db"))

    import sqlite3
    assert isinstance(conn, sqlite3.Connection)
    conn.close()


def test_get_connection_uses_turso_http_client_when_turso_url_set(monkeypatch):
    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://example-org.turso.io")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "fake-token")

    captured = {}

    class _FakeSession:
        def post(self, url, json=None, headers=None, timeout=None):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers

            class _FakeResponse:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return {
                        "results": [
                            {"type": "ok", "response": {"type": "execute", "result": {
                                "cols": [], "rows": [],
                            }}},
                            {"type": "ok", "response": {"type": "close"}},
                        ]
                    }

            return _FakeResponse()

        def close(self):
            pass

    monkeypatch.setattr(database.requests, "Session", _FakeSession)

    conn = database.get_connection()

    assert isinstance(conn, database._TursoConnection)
    assert isinstance(conn._conn, database._TursoHttpClient)
    assert conn._conn._base_url == "https://example-org.turso.io"

    # get_connection issues a PRAGMA statement on the fresh connection --
    # confirms it actually goes over the HTTP client, not a native libsql:// socket.
    assert captured["url"] == "https://example-org.turso.io/v2/pipeline"
    assert captured["headers"]["Authorization"] == "Bearer fake-token"
