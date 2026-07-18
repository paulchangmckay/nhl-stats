from etl.load_play_by_play import _extract_event


def test_extract_event_shot_on_goal():
    play = {
        "eventId": 103,
        "periodDescriptor": {"number": 1},
        "timeInPeriod": "00:08",
        "situationCode": "1551",
        "typeDescKey": "shot-on-goal",
        "details": {
            "xCoord": 56, "yCoord": -39, "zoneCode": "O", "shotType": "wrist",
            "shootingPlayerId": 8483495, "goalieInNetId": 8480045,
            "eventOwnerTeamId": 1,
        },
    }
    row = _extract_event(game_id=2024020001, play=play)

    assert row["game_id"] == 2024020001
    assert row["event_id"] == 103
    assert row["period"] == 1
    assert row["time_in_period"] == "00:08"
    assert row["situation_code"] == "1551"
    assert row["event_type"] == "shot-on-goal"
    assert row["zone_code"] == "O"
    assert row["x_coord"] == 56
    assert row["y_coord"] == -39
    assert row["shot_type"] == "wrist"
    assert row["event_owner_team_id"] == 1
    assert row["shooting_player_id"] == 8483495
    assert row["goalie_in_net_id"] == 8480045
    assert row["blocking_player_id"] is None
    assert row["assist1_player_id"] is None
    assert '"shootingPlayerId": 8483495' in row["details_json"]


def test_extract_event_goal_uses_scoring_player_id_as_shooter():
    play = {
        "eventId": 274,
        "periodDescriptor": {"number": 1},
        "timeInPeriod": "08:39",
        "situationCode": "1551",
        "typeDescKey": "goal",
        "details": {
            "scoringPlayerId": 8476474, "assist1PlayerId": 8480192,
            "eventOwnerTeamId": 1,
        },
    }
    row = _extract_event(game_id=2024020001, play=play)

    assert row["shooting_player_id"] == 8476474
    assert row["assist1_player_id"] == 8480192
    assert row["assist2_player_id"] is None


def test_extract_event_sparse_details_event_type():
    play = {
        "eventId": 152,
        "periodDescriptor": {"number": 1},
        "timeInPeriod": "00:00",
        "situationCode": "1551",
        "typeDescKey": "period-start",
    }
    row = _extract_event(game_id=2024020001, play=play)

    assert row["event_type"] == "period-start"
    assert row["shooting_player_id"] is None
    assert row["details_json"] == "{}"


from src import database


def test_run_does_not_duplicate_events_on_second_invocation(conn, monkeypatch):
    # season_id/home_team_id/away_team_id are FK-referenced (seasons/teams)
    # under the conn fixture's PRAGMA foreign_keys=ON; left None here since
    # this test only needs a valid, pending games row to exist (bug-009 in
    # .wolf/buglog.json covers the same gap found in Task 1's own tests).
    #
    # game_events.event_owner_team_id is also FK-referenced (teams); in
    # production teams are already populated by load_teams.py before
    # play-by-play loads, but this test's fake_plays sets eventOwnerTeamId=1,
    # so team_id=1 must be seeded here too (same class of gap as bug-009,
    # logged separately in .wolf/buglog.json).
    database.upsert_team(conn, {
        "team_id": 1, "abbrev": "TST", "common_name": "Test", "place_name": "Test",
        "conference": None, "division": None,
    })
    database.insert_game(conn, {
        "game_id": 2024020001, "season_id": None, "game_type": 2,
        "game_date": "2024-10-04", "venue": None, "home_team_id": None,
        "away_team_id": None, "home_score": 1, "away_score": 4,
        "last_period_type": "REG", "game_state": "OFF",
    })
    conn.commit()

    fake_plays = {"plays": [{
        "eventId": 103, "periodDescriptor": {"number": 1}, "timeInPeriod": "00:08",
        "situationCode": "1551", "typeDescKey": "shot-on-goal",
        "details": {"xCoord": 56, "yCoord": -39, "shootingPlayerId": 8483495,
                     "eventOwnerTeamId": 1},
    }]}

    import etl.load_play_by_play as module
    monkeypatch.setattr(module.api_client, "get_play_by_play", lambda gid: fake_plays)
    monkeypatch.setattr(module.time, "sleep", lambda s: None)

    module.run(conn)
    # game_events now exists for this game, so a second run must find nothing pending
    module.run(conn)

    count = conn.execute("SELECT COUNT(*) AS c FROM game_events").fetchone()["c"]
    assert count == 1


def test_run_stubs_unseeded_event_owner_team_before_insert(conn, monkeypatch):
    """Regression for Finding 1: event_owner_team_id is FK-referenced (teams)
    but a relocated/historical team (e.g. Arizona Coyotes, team_id 53) may
    not yet be in the teams table. run() must stub it before
    insert_game_event, or the FK constraint raises and the game is dropped."""
    database.insert_game(conn, {
        "game_id": 2020020001, "season_id": None, "game_type": 2,
        "game_date": "2020-10-04", "venue": None, "home_team_id": None,
        "away_team_id": None, "home_score": 1, "away_score": 4,
        "last_period_type": "REG", "game_state": "OFF",
    })
    conn.commit()

    fake_plays = {"plays": [{
        "eventId": 103, "periodDescriptor": {"number": 1}, "timeInPeriod": "00:08",
        "situationCode": "1551", "typeDescKey": "shot-on-goal",
        "details": {"xCoord": 56, "yCoord": -39, "shootingPlayerId": 8483495,
                     "eventOwnerTeamId": 53},
    }]}

    import etl.load_play_by_play as module
    monkeypatch.setattr(module.api_client, "get_play_by_play", lambda gid: fake_plays)
    monkeypatch.setattr(module.time, "sleep", lambda s: None)

    module.run(conn)  # must not raise IntegrityError

    team_row = conn.execute("SELECT 1 FROM teams WHERE team_id = ?", (53,)).fetchone()
    event_row = conn.execute(
        "SELECT event_owner_team_id FROM game_events WHERE game_id = ?", (2020020001,)
    ).fetchone()
    assert team_row is not None
    assert event_row is not None
    assert event_row["event_owner_team_id"] == 53
