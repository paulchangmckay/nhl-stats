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


def _stub_game(conn, game_id):
    """game_events/player_shifts both FK-reference games(game_id) with the
    conn fixture's PRAGMA foreign_keys=ON; a minimal games row is required
    before inserting rows against it (bug-009, see .wolf/buglog.json)."""
    database.insert_game(conn, {
        "game_id": game_id, "season_id": None, "game_type": None,
        "game_date": "2024-01-01", "venue": None,
        "home_team_id": None, "away_team_id": None, "game_state": None,
    })
    conn.commit()


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


def test_insert_game_event_is_idempotent(conn):
    _stub_game(conn, 100)
    database.ensure_player_stub(conn, 1)
    event = {
        "game_id": 100, "event_id": 1, "period": 1, "time_in_period": "00:08",
        "situation_code": "1551", "event_type": "shot-on-goal", "zone_code": "O",
        "x_coord": 56, "y_coord": -39, "shot_type": "wrist",
        "event_owner_team_id": None, "shooting_player_id": 1,
        "blocking_player_id": None, "goalie_in_net_id": None,
        "assist1_player_id": None, "assist2_player_id": None,
        "details_json": "{}",
    }
    database.insert_game_event(conn, event)
    database.insert_game_event(conn, event)  # re-insert, must not duplicate
    conn.commit()

    count = conn.execute("SELECT COUNT(*) AS c FROM game_events").fetchone()["c"]
    assert count == 1


def test_insert_player_shift_is_idempotent(conn):
    _stub_game(conn, 100)
    database.ensure_player_stub(conn, 2)
    shift = {
        "game_id": 100, "shift_id": 1, "player_id": 2, "team_id": None,
        "period": 1, "start_time": "00:00", "end_time": "17:15", "duration": "17:15",
    }
    database.insert_player_shift(conn, shift)
    database.insert_player_shift(conn, shift)  # re-insert, must not duplicate
    conn.commit()

    count = conn.execute("SELECT COUNT(*) AS c FROM player_shifts").fetchone()["c"]
    assert count == 1


def test_ensure_player_stub_creates_placeholder_when_missing(conn):
    database.ensure_player_stub(conn, 999, first_name="Jacob", last_name="Markstrom")
    conn.commit()

    row = conn.execute(
        "SELECT first_name, last_name FROM players WHERE player_id = ?", (999,)
    ).fetchone()
    assert row["first_name"] == "Jacob"
    assert row["last_name"] == "Markstrom"


def test_ensure_player_stub_does_not_overwrite_existing_player(conn):
    _stub_player(conn, player_id=5, position_code="C")

    database.ensure_player_stub(conn, 5, first_name="Should", last_name="NotApply")
    conn.commit()

    row = conn.execute(
        "SELECT first_name, position_code FROM players WHERE player_id = ?", (5,)
    ).fetchone()
    assert row["first_name"] == "Test"  # from _stub_player, unchanged
    assert row["position_code"] == "C"


def test_ensure_team_stub_creates_placeholder_when_missing(conn):
    database.ensure_team_stub(conn, 999, abbrev="ARI", common_name="Coyotes", place_name="Arizona")
    conn.commit()

    row = conn.execute(
        "SELECT abbrev, common_name, place_name FROM teams WHERE team_id = ?", (999,)
    ).fetchone()
    assert row["abbrev"] == "ARI"
    assert row["common_name"] == "Coyotes"
    assert row["place_name"] == "Arizona"


def test_ensure_team_stub_does_not_overwrite_existing_team(conn):
    database.upsert_team(conn, {
        "team_id": 5, "abbrev": "BUF", "common_name": "Sabres", "place_name": "Buffalo",
        "conference": "Eastern", "division": "Atlantic",
    })
    conn.commit()

    database.ensure_team_stub(conn, 5, abbrev="XXX", common_name="Should", place_name="NotApply")
    conn.commit()

    row = conn.execute(
        "SELECT abbrev, common_name, place_name FROM teams WHERE team_id = ?", (5,)
    ).fetchone()
    assert row["abbrev"] == "BUF"  # from upsert_team, unchanged
    assert row["common_name"] == "Sabres"
    assert row["place_name"] == "Buffalo"


def test_insert_game_succeeds_for_relocated_team_when_stubbed_first(conn):
    """Regression for Finding 1: team_id 53 (Arizona Coyotes) is absent from
    load_teams' active-roster seed. ensure_team_stub must let insert_game
    succeed for a game referencing it instead of raising IntegrityError."""
    database.ensure_team_stub(conn, 53, abbrev="ARI", common_name="Coyotes", place_name="Arizona")
    database.ensure_team_stub(conn, 7, abbrev="BUF", common_name="Sabres", place_name="Buffalo")
    conn.commit()

    database.insert_game(conn, {
        "game_id": 2021020001, "season_id": None, "game_type": 2,
        "game_date": "2021-10-04", "venue": None,
        "home_team_id": 53, "away_team_id": 7,
        "home_score": None, "away_score": None,
        "last_period_type": None, "game_state": None,
    })  # must not raise IntegrityError
    conn.commit()

    game_row = conn.execute(
        "SELECT game_id, home_team_id, away_team_id FROM games WHERE game_id = ?",
        (2021020001,),
    ).fetchone()
    assert game_row is not None
    assert game_row["home_team_id"] == 53
    assert game_row["away_team_id"] == 7
