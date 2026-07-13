import pytest

from src import database


@pytest.fixture
def conn(tmp_path):
    c = database.get_connection(db_path=str(tmp_path / "test.db"))
    database.create_all_tables(c)
    yield c
    c.close()
