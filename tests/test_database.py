from src import database


def _stub_player(conn, player_id, position_code=None):
    database.upsert_player_stub(conn, {
        "player_id": player_id,
        "first_name": "Test",
        "last_name": "Player",
        "position_code": position_code,
        "shoots_catches": None,
    })
    conn.commit()


def _position_code(conn, player_id):
    row = conn.execute(
        "SELECT position_code FROM players WHERE player_id = ?", (player_id,)
    ).fetchone()
    return row["position_code"]


def test_upsert_player_enrichment_fills_null_position_code(conn):
    """Regression for bug-001: a stub player with no position_code gets it
    filled in from the landing API's `position` field."""
    _stub_player(conn, player_id=1, position_code=None)

    database.upsert_player_enrichment(conn, {"player_id": 1, "position_code": "C"})
    conn.commit()

    assert _position_code(conn, 1) == "C"


def test_upsert_player_enrichment_preserves_existing_position_code_when_api_returns_none(conn):
    """Regression for bug-001's fill-only invariant: enrichment must never
    null out a column another phase already populated, even when the
    landing API has nothing for that field on this pass."""
    _stub_player(conn, player_id=2, position_code="D")

    database.upsert_player_enrichment(conn, {"player_id": 2, "position_code": None})
    conn.commit()

    assert _position_code(conn, 2) == "D"


def test_upsert_player_enrichment_always_overwrites_draft_fields(conn):
    """Draft/bio fields are authoritative from enrichment on every run,
    unlike the fill-only bio/position columns — this is intentionally NOT
    wrapped in COALESCE in upsert_player_enrichment."""
    _stub_player(conn, player_id=3)
    database.upsert_player_enrichment(conn, {"player_id": 3, "draft_year": 2015})
    conn.commit()

    database.upsert_player_enrichment(conn, {"player_id": 3, "draft_year": 2020})
    conn.commit()

    row = conn.execute(
        "SELECT draft_year FROM players WHERE player_id = ?", (3,)
    ).fetchone()
    assert row["draft_year"] == 2020
