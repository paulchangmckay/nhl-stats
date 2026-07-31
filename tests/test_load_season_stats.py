import pytest

from src import database
import etl.load_season_stats as module


def _stub_team(conn, team_id=1, abbrev="TST"):
    database.upsert_team(conn, {
        "team_id": team_id, "abbrev": abbrev, "common_name": "Test",
        "place_name": "Test", "conference": None, "division": None,
    })


def _stub_game(conn, game_id, season_id, game_type, team_id=1):
    database.upsert_season(conn, {
        "season_id": season_id,
        "start_year": int(season_id[:4]),
        "end_year": int(season_id[4:]),
    })
    database.insert_game(conn, {
        "game_id": game_id, "season_id": season_id, "game_type": game_type,
        "game_date": "2024-10-04", "venue": None,
        "home_team_id": team_id, "away_team_id": team_id,
        "home_score": 3, "away_score": 2,
        "last_period_type": "REG", "game_state": "OFF",
    })


def test_fill_missing_skater_season_stats_aggregates_from_game_stats(conn):
    _stub_team(conn)
    _stub_game(conn, 2024020001, "20242025", 2)
    _stub_game(conn, 2024020002, "20242025", 2)
    database.upsert_player_stub(conn, {
        "player_id": 999, "first_name": "Test", "last_name": "Player",
        "position_code": "C",
    })
    database.insert_player_game_stats(conn, {
        "game_id": 2024020001, "player_id": 999, "team_id": 1,
        "goals": 1, "assists": 2, "points": 3, "plus_minus": 1, "pim": 2,
        "hits": 0, "shots_on_goal": 4, "blocked_shots": 0, "toi": "15:00",
    })
    database.insert_player_game_stats(conn, {
        "game_id": 2024020002, "player_id": 999, "team_id": 1,
        "goals": 0, "assists": 1, "points": 1, "plus_minus": -1, "pim": 0,
        "hits": 0, "shots_on_goal": 2, "blocked_shots": 0, "toi": "17:00",
    })
    conn.commit()

    n = module._fill_missing_skater_season_stats(conn, "20242025", 2)

    assert n == 1
    row = conn.execute(
        "SELECT * FROM player_season_stats WHERE player_id = 999 "
        "AND season_id = '20242025' AND game_type = 2"
    ).fetchone()
    assert row["gp"] == 2
    assert row["goals"] == 1
    assert row["assists"] == 3
    assert row["points"] == 4
    assert row["plus_minus"] == 0
    assert row["pim"] == 2
    assert row["shots"] == 6
    assert row["shooting_pct"] == pytest.approx(1 / 6 * 100, abs=0.01)
    assert row["avg_toi"] == "16:00"
    assert row["team_abbrevs"] == "TST"
    assert row["position_code"] == "C"


def test_fill_missing_skater_season_stats_skips_goalies(conn):
    _stub_team(conn)
    _stub_game(conn, 2024020001, "20242025", 2)
    database.upsert_player_stub(conn, {
        "player_id": 998, "first_name": "Backup", "last_name": "Goalie",
        "position_code": "G",
    })
    database.insert_player_game_stats(conn, {
        "game_id": 2024020001, "player_id": 998, "team_id": 1,
        "goals": 0, "assists": 0, "points": 0, "plus_minus": 0, "pim": 0,
        "hits": 0, "shots_on_goal": 0, "blocked_shots": 0, "toi": "60:00",
    })
    conn.commit()

    n = module._fill_missing_skater_season_stats(conn, "20242025", 2)

    assert n == 0
    row = conn.execute(
        "SELECT * FROM player_season_stats WHERE player_id = 998"
    ).fetchone()
    assert row is None


def test_fill_missing_skater_season_stats_skips_players_already_present(conn):
    _stub_team(conn)
    _stub_game(conn, 2024020001, "20242025", 2)
    database.upsert_player_stub(conn, {
        "player_id": 997, "first_name": "Already", "last_name": "Synced",
        "position_code": "C",
    })
    database.insert_player_game_stats(conn, {
        "game_id": 2024020001, "player_id": 997, "team_id": 1,
        "goals": 5, "assists": 5, "points": 10, "plus_minus": 2, "pim": 0,
        "hits": 0, "shots_on_goal": 10, "blocked_shots": 0, "toi": "18:00",
    })
    database.upsert_season_stats(conn, {
        "player_id": 997, "season_id": "20242025", "game_type": 2,
        "team_abbrevs": "TST", "position_code": "C",
        "gp": 1, "goals": 1, "assists": 1, "points": 2,
    })
    conn.commit()

    n = module._fill_missing_skater_season_stats(conn, "20242025", 2)

    assert n == 0
    row = conn.execute(
        "SELECT goals FROM player_season_stats WHERE player_id = 997"
    ).fetchone()
    assert row["goals"] == 1  # untouched, not overwritten by the fallback aggregation
