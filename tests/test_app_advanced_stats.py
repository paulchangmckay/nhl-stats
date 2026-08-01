import app as app_module
from app import _fetch_player_advanced, _fetch_team_advanced
from src import database

HOME = 1
AWAY = 2


def _seed_season_row(conn, player_id, season_id, strength_state, cf, ca, ff, fa,
                      hdcf, hdca, primary_points, team_abbrevs="HOM",
                      icf=0, ihdcf=0, rebounds_created=0, deflections=0, points=0,
                      toi_seconds=900):
    conn.execute("""
        INSERT INTO player_season_advanced_stats
            (player_id, season_id, game_type, team_abbrevs, strength_state,
             cf, ca, ff, fa, hdcf, hdca, gf, ga, primary_points, toi_seconds, gp,
             icf, ihdcf, rebounds_created, deflections, points)
        VALUES (?, ?, 2, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, ?, ?, 20, ?, ?, ?, ?, ?)
    """, (player_id, season_id, team_abbrevs, strength_state, cf, ca, ff, fa,
          hdcf, hdca, primary_points, toi_seconds,
          icf, ihdcf, rebounds_created, deflections, points))
    conn.commit()


def _seed_percentile_row(conn, player_id, season_id, strength_state, cf_pctile):
    conn.execute("""
        INSERT INTO player_advanced_percentiles
            (season_id, player_id, strength_state, position_group,
             cf_pct_pctile, ff_pct_pctile, hdcf_pct_pctile, primary_points_pctile)
        VALUES (?, ?, ?, 'F', ?, 50.0, 50.0, 50.0)
    """, (season_id, player_id, strength_state, cf_pctile))
    conn.commit()


def _seed_team_season_row(conn, team_id, season_id, strength_state, gf, ga, shots_for, shots_against):
    conn.execute("""
        INSERT INTO team_season_advanced_stats
            (team_id, season_id, game_type, strength_state,
             cf, ca, ff, fa, gf, ga, shots_for, shots_against)
        VALUES (?, ?, 2, ?, 1, 1, 1, 1, ?, ?, ?, ?)
    """, (team_id, season_id, strength_state, gf, ga, shots_for, shots_against))
    conn.commit()


def test_fetch_player_advanced_returns_per_strength_state_breakdown(conn):
    database.upsert_player_stub(conn, {
        "player_id": 1, "first_name": "Test", "last_name": "Player",
        "position_code": "C", "shoots_catches": None,
    })
    database.upsert_team(conn, {"team_id": HOME, "abbrev": "HOM", "common_name": "Home",
                                 "place_name": "Home", "conference": None, "division": None})
    _seed_season_row(conn, 1, "20242025", "5v5", cf=60, ca=40, ff=45, fa=30, hdcf=10, hdca=5, primary_points=15)
    _seed_percentile_row(conn, 1, "20242025", "5v5", cf_pctile=75.0)

    result = _fetch_player_advanced(conn, player_id=1, season_id="20242025")

    assert "5v5" in result["strength_states"]
    s = result["strength_states"]["5v5"]
    assert s["cf"] == 60
    assert s["ca"] == 40
    assert s["cf_pct"] == 60.0  # 60 / (60+40) * 100
    assert s["primary_points"] == 15
    assert s["cf_pctile"] == 75.0


def test_fetch_player_advanced_includes_trend_across_seasons(conn):
    database.upsert_player_stub(conn, {
        "player_id": 1, "first_name": "Test", "last_name": "Player",
        "position_code": "C", "shoots_catches": None,
    })
    _seed_season_row(conn, 1, "20232024", "5v5", cf=50, ca=50, ff=40, fa=40, hdcf=5, hdca=5, primary_points=10)
    _seed_season_row(conn, 1, "20242025", "5v5", cf=60, ca=40, ff=45, fa=30, hdcf=10, hdca=5, primary_points=15)

    result = _fetch_player_advanced(conn, player_id=1, season_id="20242025")

    trend_seasons = [t["season_id"] for t in result["trend"]]
    assert trend_seasons == ["20232024", "20242025"]


def test_fetch_player_advanced_pdo_comes_from_team_context(conn):
    database.upsert_player_stub(conn, {
        "player_id": 1, "first_name": "Test", "last_name": "Player",
        "position_code": "C", "shoots_catches": None,
    })
    database.upsert_team(conn, {"team_id": HOME, "abbrev": "HOM", "common_name": "Home",
                                 "place_name": "Home", "conference": None, "division": None})
    _seed_season_row(conn, 1, "20242025", "5v5", cf=60, ca=40, ff=45, fa=30, hdcf=10, hdca=5,
                      primary_points=15, team_abbrevs="HOM")
    _seed_team_season_row(conn, HOME, "20242025", "5v5", gf=30, ga=25, shots_for=300, shots_against=280)

    result = _fetch_player_advanced(conn, player_id=1, season_id="20242025")

    # PDO = (shooting% + save%) * 1000 = (30/300 + (280-25)/280) * 1000
    expected_pdo = round((30 / 300 + (280 - 25) / 280) * 1000, 1)
    assert result["pdo"] == expected_pdo


def test_fetch_team_advanced_returns_per_strength_state_breakdown(conn):
    database.upsert_team(conn, {"team_id": HOME, "abbrev": "HOM", "common_name": "Home",
                                 "place_name": "Home", "conference": None, "division": None})
    _seed_team_season_row(conn, HOME, "20242025", "5v5", gf=30, ga=25, shots_for=300, shots_against=280)

    result = _fetch_team_advanced(conn, team_abbrev="HOM", season_id="20242025")

    assert "5v5" in result["strength_states"]
    assert result["strength_states"]["5v5"]["gf"] == 30
    assert result["strength_states"]["5v5"]["ga"] == 25


def test_players_stats_season_query_includes_cf_pct_5v5(conn, monkeypatch):
    # Bug caught in code review: PlayerTable's new CF% (5v5) teaser column
    # read a field /api/players/stats never returned, so it always rendered
    # "-" -- this test drives the real route (not just the isolated advanced-
    # stats helpers) to make sure the season-specific branch actually joins
    # player_season_advanced_stats and computes the percentage.
    database.upsert_player_stub(conn, {
        "player_id": 1, "first_name": "Test", "last_name": "Player",
        "position_code": "C", "shoots_catches": None,
    })
    conn.execute("""
        INSERT INTO player_season_stats
            (player_id, season_id, game_type, team_abbrevs, position_code, gp, goals, assists,
             points, plus_minus, pim, pp_goals, sh_goals, shots, shooting_pct, avg_toi,
             wins, losses, ot_losses, shutouts, save_pct, gaa)
        VALUES (1, '20242025', 2, 'HOM', 'C', 10, 5, 5, 10, 0, 0, 0, 0, 20, 25.0, '15:00',
                NULL, NULL, NULL, NULL, NULL, NULL)
    """)
    conn.execute("""
        INSERT INTO player_season_advanced_stats
            (player_id, season_id, game_type, team_abbrevs, strength_state,
             cf, ca, ff, fa, hdcf, hdca, gf, ga, primary_points, toi_seconds, gp)
        VALUES (1, '20242025', 2, 'HOM', '5v5', 60, 40, 45, 30, 10, 5, 6, 4, 10, 9000, 10)
    """)
    conn.commit()

    monkeypatch.setattr(app_module, "get_connection", lambda: conn)
    client = app_module.app.test_client()
    resp = client.get("/api/players/stats?seasons=20242025")

    assert resp.status_code == 200
    player = next(p for p in resp.get_json() if p["player_id"] == 1)
    assert player["cf_pct_5v5"] == 60.0


def test_fetch_player_advanced_includes_rate_stats_for_5v5_only(conn):
    database.upsert_player_stub(conn, {
        "player_id": 1, "first_name": "Test", "last_name": "Player",
        "position_code": "C", "shoots_catches": None,
    })
    database.upsert_team(conn, {"team_id": HOME, "abbrev": "HOM", "common_name": "Home",
                                 "place_name": "Home", "conference": None, "division": None})
    _seed_season_row(conn, 1, "20242025", "5v5", cf=60, ca=40, ff=45, fa=30, hdcf=10, hdca=5,
                      primary_points=15, icf=30, ihdcf=8, rebounds_created=4, deflections=2,
                      points=20, toi_seconds=3600)
    _seed_season_row(conn, 1, "20242025", "5v4", cf=20, ca=5, ff=15, fa=3, hdcf=4, hdca=1,
                      primary_points=5, icf=99, ihdcf=99, rebounds_created=99, deflections=99,
                      points=99, toi_seconds=900)

    result = _fetch_player_advanced(conn, player_id=1, season_id="20242025")

    s5v5 = result["strength_states"]["5v5"]
    assert s5v5["shots_per60"] == 30.0
    assert s5v5["chances_per60"] == 8.0
    assert s5v5["rebounds_created_per60"] == 4.0
    assert s5v5["deflections_per60"] == 2.0
    assert s5v5["points_per60"] == 20.0
    assert s5v5["primary_points_per60"] == 15.0
    assert "shots_per60" not in result["strength_states"]["5v4"]


def test_fetch_player_advanced_zscore_null_when_no_zscore_row(conn):
    database.upsert_player_stub(conn, {
        "player_id": 1, "first_name": "Test", "last_name": "Player",
        "position_code": "C", "shoots_catches": None,
    })
    database.upsert_team(conn, {"team_id": HOME, "abbrev": "HOM", "common_name": "Home",
                                 "place_name": "Home", "conference": None, "division": None})
    _seed_season_row(conn, 1, "20242025", "5v5", cf=60, ca=40, ff=45, fa=30, hdcf=10, hdca=5,
                      primary_points=15, icf=30, toi_seconds=3600)

    result = _fetch_player_advanced(conn, player_id=1, season_id="20242025")
    assert result["strength_states"]["5v5"]["shots_per60_z"] is None


def test_fetch_player_advanced_zscore_populated_when_zscore_row_exists(conn):
    database.upsert_player_stub(conn, {
        "player_id": 1, "first_name": "Test", "last_name": "Player",
        "position_code": "C", "shoots_catches": None,
    })
    database.upsert_team(conn, {"team_id": HOME, "abbrev": "HOM", "common_name": "Home",
                                 "place_name": "Home", "conference": None, "division": None})
    _seed_season_row(conn, 1, "20242025", "5v5", cf=60, ca=40, ff=45, fa=30, hdcf=10, hdca=5,
                      primary_points=15, icf=30, toi_seconds=3600)
    database.upsert_player_rate_zscores(conn, {
        "season_id": "20242025", "player_id": 1, "position_group": "F",
        "shots_per60_z": 1.23, "chances_per60_z": 0.5, "rebounds_created_per60_z": -0.2,
        "deflections_per60_z": 0.0, "points_per60_z": 0.9, "primary_points_per60_z": 0.8,
    })
    conn.commit()

    result = _fetch_player_advanced(conn, player_id=1, season_id="20242025")
    assert result["strength_states"]["5v5"]["shots_per60_z"] == 1.23


def test_players_stats_season_query_includes_shots_per60_5v5(conn, monkeypatch):
    database.upsert_player_stub(conn, {
        "player_id": 1, "first_name": "Test", "last_name": "Player",
        "position_code": "C", "shoots_catches": None,
    })
    conn.execute("""
        INSERT INTO player_season_stats
            (player_id, season_id, game_type, team_abbrevs, position_code, gp, goals, assists,
             points, plus_minus, pim, pp_goals, sh_goals, shots, shooting_pct, avg_toi,
             wins, losses, ot_losses, shutouts, save_pct, gaa)
        VALUES (1, '20242025', 2, 'HOM', 'C', 10, 5, 5, 10, 0, 0, 0, 0, 20, 25.0, '15:00',
                NULL, NULL, NULL, NULL, NULL, NULL)
    """)
    conn.execute("""
        INSERT INTO player_season_advanced_stats
            (player_id, season_id, game_type, team_abbrevs, strength_state,
             cf, ca, ff, fa, hdcf, hdca, gf, ga, primary_points, toi_seconds, gp,
             icf, ihdcf, rebounds_created, deflections, points)
        VALUES (1, '20242025', 2, 'HOM', '5v5', 60, 40, 45, 30, 10, 5, 6, 4, 10, 3600, 10,
                24, 8, 4, 2, 20)
    """)
    conn.commit()

    monkeypatch.setattr(app_module, "get_connection", lambda: conn)
    client = app_module.app.test_client()
    resp = client.get("/api/players/stats?seasons=20242025")

    assert resp.status_code == 200
    player = next(p for p in resp.get_json() if p["player_id"] == 1)
    assert player["shots_per60_5v5"] == 24.0


def test_fetch_player_advanced_handles_null_hd_stats_without_crashing(conn):
    # 2017-18/2018-19-shaped row: hdcf/hdca/ihdcf are all NULL (no rink-side
    # data for that era). hdcf_pct and chances_per60 must degrade to None
    # instead of raising TypeError on None + None / None / toi_hours.
    database.upsert_player_stub(conn, {
        "player_id": 1, "first_name": "Test", "last_name": "Player",
        "position_code": "C", "shoots_catches": None,
    })
    database.upsert_team(conn, {"team_id": HOME, "abbrev": "HOM", "common_name": "Home",
                                 "place_name": "Home", "conference": None, "division": None})
    _seed_season_row(conn, 1, "20172018", "5v5", cf=60, ca=40, ff=45, fa=30,
                      hdcf=None, hdca=None, primary_points=15, icf=30, ihdcf=None,
                      toi_seconds=3600)

    result = _fetch_player_advanced(conn, player_id=1, season_id="20172018")

    s5v5 = result["strength_states"]["5v5"]
    assert s5v5["hdcf_pct"] is None
    assert s5v5["chances_per60"] is None
