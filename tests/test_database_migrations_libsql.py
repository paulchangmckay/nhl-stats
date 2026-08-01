import libsql

from src.database import _TursoConnection, run_migrations, create_all_tables


def test_run_migrations_is_idempotent_against_libsql_backend(tmp_path):
    raw = libsql.connect(str(tmp_path / "migrations_test.db"))
    conn = _TursoConnection(raw)
    # Set up the full schema which includes calling run_migrations once
    create_all_tables(conn)

    # Running migrations again must not raise, even against libsql backend
    # which raises ValueError for duplicate columns instead of sqlite3.OperationalError.
    run_migrations(conn)
