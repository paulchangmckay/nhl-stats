from src import database
import etl.compute_advanced_stats as module

HOME = 1
AWAY = 2


def _seed_game(conn, game_id, season_id="20242025", game_type=2):
    database.upsert_season(conn, {"season_id": season_id, "start_year": 2024, "end_year": 2025})
    database.upsert_team(conn, {"team_id": HOME, "abbrev": "HOM", "common_name": "Home",
                                 "place_name": "Home", "conference": None, "division": None})
    database.upsert_team(conn, {"team_id": AWAY, "abbrev": "AWY", "common_name": "Away",
                                 "place_name": "Away", "conference": None, "division": None})
    database.insert_game(conn, {
        "game_id": game_id, "season_id": season_id, "game_type": game_type,
        "game_date": "2024-10-04", "venue": None, "home_team_id": HOME,
        "away_team_id": AWAY, "home_score": 1, "away_score": 0,
        "last_period_type": "REG", "game_state": "OFF",
    })


def _seed_event(conn, game_id, event_id, event_owner_team_id=HOME):
    database.insert_game_event(conn, {
        "game_id": game_id, "event_id": event_id, "period": 1,
        "time_in_period": "00:10", "situation_code": "1551",
        "event_type": "shot-on-goal", "zone_code": "O", "x_coord": 10,
        "y_coord": 0, "shot_type": "wrist", "event_owner_team_id": event_owner_team_id,
        "shooting_player_id": None, "blocking_player_id": None, "goalie_in_net_id": None,
        "assist1_player_id": None, "assist2_player_id": None, "details_json": "{}",
        "home_team_defending_side": "right",
    })


def _seed_shift(conn, game_id, shift_id, player_id, team_id, position_code="C"):
    database.upsert_player_stub(conn, {
        "player_id": player_id, "first_name": "Test", "last_name": "Player",
        "position_code": position_code, "shoots_catches": None,
    })
    database.insert_player_shift(conn, {
        "game_id": game_id, "shift_id": shift_id, "player_id": player_id,
        "team_id": team_id, "period": 1, "start_time": "00:00",
        "end_time": "20:00", "duration": "20:00",
    })


def test_run_processes_pending_game_and_is_idempotent(conn):
    _seed_game(conn, 2024020001)
    _seed_shift(conn, 2024020001, 1, player_id=1, team_id=HOME)
    _seed_shift(conn, 2024020001, 2, player_id=2, team_id=AWAY)
    _seed_event(conn, 2024020001, 1)
    conn.commit()

    module.run(conn)
    module.run(conn)  # second run must not duplicate

    count = conn.execute(
        "SELECT COUNT(*) AS c FROM player_game_advanced_stats WHERE game_id = 2024020001"
    ).fetchone()["c"]
    assert count == 2  # both on-ice skaters (shooter's team + opponent) get a 5v5 row

    row = conn.execute(
        "SELECT cf FROM player_game_advanced_stats WHERE game_id = 2024020001 AND player_id = 1"
    ).fetchone()
    assert row["cf"] == 1


def test_compute_season_aggregates_sums_across_games(conn):
    _seed_game(conn, 2024020001)
    _seed_game(conn, 2024020002)
    _seed_shift(conn, 2024020001, 1, player_id=1, team_id=HOME)
    _seed_shift(conn, 2024020002, 1, player_id=1, team_id=HOME)
    _seed_event(conn, 2024020001, 1)
    _seed_event(conn, 2024020002, 1)
    conn.commit()

    module.run(conn)
    module.compute_season_aggregates(conn, season_id="20242025", game_type=2)

    row = conn.execute("""
        SELECT cf, gp, team_abbrevs FROM player_season_advanced_stats
        WHERE player_id = 1 AND season_id = '20242025' AND game_type = 2 AND strength_state = '5v5'
    """).fetchone()
    assert row["cf"] == 2
    assert row["gp"] == 2
    assert row["team_abbrevs"] == "HOM"


def test_compute_percentiles_ranks_three_player_population(conn):
    # Three forwards with distinct season CF totals at 5v5, all clearing the
    # 10-GP floor; the top scorer should land at the 100th percentile.
    for player_id, cf, gp in [(1, 30, 12), (2, 20, 12), (3, 10, 12)]:
        database.upsert_player_stub(conn, {
            "player_id": player_id, "first_name": "P", "last_name": str(player_id),
            "position_code": "C", "shoots_catches": None,
        })
        conn.execute("""
            INSERT INTO player_season_advanced_stats
                (player_id, season_id, game_type, team_abbrevs, strength_state,
                 cf, ca, ff, fa, hdcf, hdca, gf, ga, primary_points, toi_seconds, gp)
            VALUES (?, '20242025', 2, 'HOM', '5v5', ?, 5, ?, 5, 1, 1, 1, 1, 1, 900, ?)
        """, (player_id, cf, cf, gp))
    conn.commit()

    module.compute_percentiles(conn, season_id="20242025")

    top = conn.execute(
        "SELECT cf_pct_pctile FROM player_advanced_percentiles WHERE player_id = 1"
    ).fetchone()
    bottom = conn.execute(
        "SELECT cf_pct_pctile FROM player_advanced_percentiles WHERE player_id = 3"
    ).fetchone()
    assert top["cf_pct_pctile"] == 100.0
    assert bottom["cf_pct_pctile"] == 0.0


def test_compute_percentiles_excludes_players_below_gp_floor(conn):
    database.upsert_player_stub(conn, {
        "player_id": 1, "first_name": "P", "last_name": "1",
        "position_code": "C", "shoots_catches": None,
    })
    conn.execute("""
        INSERT INTO player_season_advanced_stats
            (player_id, season_id, game_type, team_abbrevs, strength_state,
             cf, ca, ff, fa, hdcf, hdca, gf, ga, primary_points, toi_seconds, gp)
        VALUES (1, '20242025', 2, 'HOM', '5v5', 10, 5, 10, 5, 1, 1, 1, 1, 1, 900, 3)
    """)
    conn.commit()

    module.compute_percentiles(conn, season_id="20242025")

    row = conn.execute(
        "SELECT * FROM player_advanced_percentiles WHERE player_id = 1"
    ).fetchone()
    assert row is None  # below the 10-GP floor, no percentile row created
