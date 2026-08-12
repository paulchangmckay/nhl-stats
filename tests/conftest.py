import pytest

from src import database


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
    c = database.get_connection(db_path=str(tmp_path / "test.db"))
    database.create_all_tables(c)
    yield c
    c.close()
