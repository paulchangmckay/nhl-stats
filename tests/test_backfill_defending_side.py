from src import database
import etl.backfill_defending_side as module


def test_run_updates_existing_events_with_defending_side(conn, monkeypatch):
    database.upsert_team(conn, {
        "team_id": 1, "abbrev": "TST", "common_name": "Test", "place_name": "Test",
        "conference": None, "division": None,
    })
    database.insert_game(conn, {
        "game_id": 2024020001, "season_id": None, "game_type": 2,
        "game_date": "2024-10-04", "venue": None, "home_team_id": None,
        "away_team_id": None, "home_score": 1, "away_score": 0,
        "last_period_type": "REG", "game_state": "OFF",
    })
    database.insert_game_event(conn, {
        "game_id": 2024020001, "event_id": 103, "period": 1,
        "time_in_period": "00:08", "situation_code": "1551",
        "event_type": "shot-on-goal", "zone_code": "O", "x_coord": 56,
        "y_coord": -39, "shot_type": "wrist", "event_owner_team_id": 1,
        "shooting_player_id": None, "blocking_player_id": None,
        "goalie_in_net_id": None, "assist1_player_id": None,
        "assist2_player_id": None, "details_json": "{}",
        "home_team_defending_side": None,
    })
    conn.commit()

    fake_plays = {"plays": [{
        "eventId": 103, "periodDescriptor": {"number": 1}, "timeInPeriod": "00:08",
        "situationCode": "1551", "typeDescKey": "shot-on-goal",
        "homeTeamDefendingSide": "right",
        "details": {"xCoord": 56, "yCoord": -39, "eventOwnerTeamId": 1},
    }]}
    monkeypatch.setattr(module.api_client, "get_play_by_play", lambda gid: fake_plays)
    monkeypatch.setattr(module.time, "sleep", lambda s: None)

    module.run(conn)

    row = conn.execute(
        "SELECT home_team_defending_side FROM game_events WHERE game_id = ? AND event_id = ?",
        (2024020001, 103),
    ).fetchone()
    assert row["home_team_defending_side"] == "right"


def test_run_skips_games_already_fully_backfilled(conn, monkeypatch):
    database.upsert_team(conn, {
        "team_id": 1, "abbrev": "TST", "common_name": "Test", "place_name": "Test",
        "conference": None, "division": None,
    })
    database.insert_game(conn, {
        "game_id": 2024020001, "season_id": None, "game_type": 2,
        "game_date": "2024-10-04", "venue": None, "home_team_id": None,
        "away_team_id": None, "home_score": 1, "away_score": 0,
        "last_period_type": "REG", "game_state": "OFF",
    })
    database.insert_game_event(conn, {
        "game_id": 2024020001, "event_id": 103, "period": 1,
        "time_in_period": "00:08", "situation_code": "1551",
        "event_type": "shot-on-goal", "zone_code": "O", "x_coord": 56,
        "y_coord": -39, "shot_type": "wrist", "event_owner_team_id": 1,
        "shooting_player_id": None, "blocking_player_id": None,
        "goalie_in_net_id": None, "assist1_player_id": None,
        "assist2_player_id": None, "details_json": "{}",
        "home_team_defending_side": "right",  # already backfilled
    })
    conn.commit()

    calls = []
    monkeypatch.setattr(module.api_client, "get_play_by_play",
                         lambda gid: calls.append(gid) or {"plays": []})
    monkeypatch.setattr(module.time, "sleep", lambda s: None)

    module.run(conn)

    assert calls == []  # already-backfilled game must not trigger a re-fetch
