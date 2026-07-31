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
