from etl.load_shifts import _extract_shift


def test_extract_shift_maps_all_fields():
    shift = {
        "id": 14376602, "playerId": 8474593, "teamId": 1, "period": 1,
        "startTime": "00:00", "endTime": "17:15", "duration": "17:15",
        "firstName": "Jacob", "lastName": "Markstrom",
    }
    row = _extract_shift(game_id=2024020001, shift=shift)

    assert row["game_id"] == 2024020001
    assert row["shift_id"] == 14376602
    assert row["player_id"] == 8474593
    assert row["team_id"] == 1
    assert row["period"] == 1
    assert row["start_time"] == "00:00"
    assert row["end_time"] == "17:15"
    assert row["duration"] == "17:15"


def test_extract_shift_handles_missing_end_time():
    shift = {
        "id": 14376999, "playerId": 8474593, "teamId": 1, "period": 3,
        "startTime": "19:58", "endTime": None, "duration": None,
        "firstName": "Jacob", "lastName": "Markstrom",
    }
    row = _extract_shift(game_id=2024020001, shift=shift)

    assert row["end_time"] is None
    assert row["duration"] is None


from src import database


def test_run_does_not_duplicate_shifts_on_second_invocation(conn, monkeypatch):
    # season_id/home_team_id/away_team_id are FK-referenced (seasons/teams)
    # under the conn fixture's PRAGMA foreign_keys=ON; left None here since
    # this test only needs a valid, pending games row to exist (bug-009 in
    # .wolf/buglog.json covers the same gap found in Task 1's own tests).
    database.insert_game(conn, {
        "game_id": 2024020001, "season_id": None, "game_type": 2,
        "game_date": "2024-10-04", "venue": None, "home_team_id": None,
        "away_team_id": None, "home_score": 1, "away_score": 4,
        "last_period_type": "REG", "game_state": "OFF",
    })
    conn.commit()

    # player_shifts.team_id is also FK-referenced (teams); seed it here since
    # this test's fake data uses a real teamId (bug-010 in .wolf/buglog.json
    # covers the identical gap found in Task 4's own idempotency test).
    database.upsert_team(conn, {
        "team_id": 1, "abbrev": "NJD", "common_name": "Devils",
        "place_name": "New Jersey", "conference": "Eastern", "division": "Metropolitan",
    })
    conn.commit()

    fake_shifts = [{
        "id": 14376602, "playerId": 8474593, "teamId": 1, "period": 1,
        "startTime": "00:00", "endTime": "17:15", "duration": "17:15",
        "firstName": "Jacob", "lastName": "Markstrom",
    }]

    import etl.load_shifts as module
    monkeypatch.setattr(module.api_client, "get_shift_chart", lambda gid: fake_shifts)
    monkeypatch.setattr(module.time, "sleep", lambda s: None)

    module.run(conn)
    module.run(conn)  # second run must find nothing pending

    count = conn.execute("SELECT COUNT(*) AS c FROM player_shifts").fetchone()["c"]
    assert count == 1


def test_run_stubs_unseeded_shift_team_before_insert(conn, monkeypatch):
    """Regression for Finding 1: player_shifts.team_id is FK-referenced
    (teams) but a relocated/historical team (e.g. Arizona Coyotes, team_id
    53) may not yet be in the teams table. run() must stub it before
    insert_player_shift, or the FK constraint raises and the game is
    dropped."""
    database.insert_game(conn, {
        "game_id": 2020020001, "season_id": None, "game_type": 2,
        "game_date": "2020-10-04", "venue": None, "home_team_id": None,
        "away_team_id": None, "home_score": 1, "away_score": 4,
        "last_period_type": "REG", "game_state": "OFF",
    })
    conn.commit()

    fake_shifts = [{
        "id": 14376602, "playerId": 8474593, "teamId": 53, "period": 1,
        "startTime": "00:00", "endTime": "17:15", "duration": "17:15",
        "firstName": "Jacob", "lastName": "Markstrom",
    }]

    import etl.load_shifts as module
    monkeypatch.setattr(module.api_client, "get_shift_chart", lambda gid: fake_shifts)
    monkeypatch.setattr(module.time, "sleep", lambda s: None)

    module.run(conn)  # must not raise IntegrityError

    team_row = conn.execute("SELECT 1 FROM teams WHERE team_id = ?", (53,)).fetchone()
    shift_row = conn.execute(
        "SELECT team_id FROM player_shifts WHERE game_id = ?", (2020020001,)
    ).fetchone()
    assert team_row is not None
    assert shift_row is not None
    assert shift_row["team_id"] == 53
