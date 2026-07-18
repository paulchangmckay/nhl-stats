from etl.load_historical_schedule import _map_game_state, _extract_game, run
from src import database


def test_map_game_state_known_value_returns_off():
    assert _map_game_state(7) == "OFF"


def test_map_game_state_unknown_value_falls_back_to_raw_string():
    assert _map_game_state(99) == "99"


def test_extract_game_maps_all_fields():
    raw = {
        "id": 2024020001, "season": 20242025, "gameType": 2,
        "gameDate": "2024-10-04", "homeTeamId": 7, "visitingTeamId": 1,
        "homeScore": 1, "visitingScore": 4, "gameStateId": 7,
    }
    game = _extract_game(raw)

    assert game.game_id == 2024020001
    assert game.season_id == "20242025"
    assert game.game_type == 2
    assert game.game_date == "2024-10-04"
    assert game.home_team_id == 7
    assert game.away_team_id == 1
    assert game.home_score == 1
    assert game.away_score == 4
    assert game.game_state == "OFF"
    assert game.venue is None
    assert game.last_period_type is None


def test_insert_game_succeeds_for_unseeded_season_when_seeded_first(conn):
    """Regression test: insert_game(conn, ...) fails with a foreign-key
    IntegrityError if the game's season_id isn't already present in the
    seasons table. run() must upsert the season before inserting games for
    it -- this proves that seeding-then-inserting works for a season_id
    that was never seen before (e.g. the older backfill seasons)."""
    conn.execute(
        "INSERT INTO teams (team_id, abbrev, common_name, place_name) "
        "VALUES (7, 'BUF', 'Sabres', 'Buffalo'), (1, 'NJD', 'Devils', 'New Jersey')"
    )

    season_id = "20202021"
    row = conn.execute(
        "SELECT 1 FROM seasons WHERE season_id = ?", (season_id,)
    ).fetchone()
    assert row is None  # sanity check: season is not yet seeded

    database.upsert_season(conn, {
        "season_id": season_id,
        "start_year": int(season_id[:4]),
        "end_year": int(season_id[4:]),
    })

    raw = {
        "id": 2020020001, "season": 20202021, "gameType": 2,
        "gameDate": "2020-10-04", "homeTeamId": 7, "visitingTeamId": 1,
        "homeScore": 1, "visitingScore": 4, "gameStateId": 7,
    }
    game = _extract_game(raw)
    database.insert_game(conn, game.__dict__)  # must not raise IntegrityError
    conn.commit()

    season_row = conn.execute(
        "SELECT season_id FROM seasons WHERE season_id = ?", (season_id,)
    ).fetchone()
    game_row = conn.execute(
        "SELECT game_id, season_id FROM games WHERE game_id = ?", (2020020001,)
    ).fetchone()

    assert season_row is not None
    assert game_row is not None
    assert game_row["season_id"] == season_id


def test_run_stubs_unseeded_team_before_inserting_game(conn, monkeypatch):
    """Regression for Finding 1: team_id 53 (Arizona Coyotes) played in the
    backfill seasons but is absent from load_teams' active-roster seed.
    run() must stub home/away team ids before insert_game, or the FK
    constraint silently drops every game for a relocated/historical team."""
    fake_game = {
        "id": 2020020001, "season": 20202021, "gameType": 2,
        "gameDate": "2020-10-04", "homeTeamId": 53, "visitingTeamId": 7,
        "homeScore": 1, "visitingScore": 4, "gameStateId": 7,
    }

    import etl.load_historical_schedule as module
    monkeypatch.setattr(module.api_client, "get_season_games", lambda season_id, game_type: [fake_game])

    run(conn)

    team_53 = conn.execute("SELECT 1 FROM teams WHERE team_id = ?", (53,)).fetchone()
    team_7 = conn.execute("SELECT 1 FROM teams WHERE team_id = ?", (7,)).fetchone()
    game_row = conn.execute(
        "SELECT home_team_id, away_team_id FROM games WHERE game_id = ?", (2020020001,)
    ).fetchone()

    assert team_53 is not None
    assert team_7 is not None
    assert game_row is not None
    assert game_row["home_team_id"] == 53
    assert game_row["away_team_id"] == 7
