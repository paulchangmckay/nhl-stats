import app as app_module
from app import _fetch_player_advanced, _fetch_team_advanced
from src import database

HOME = 1
AWAY = 2


def _seed_season_row(conn, player_id, season_id, strength_state, cf, ca, ff, fa,
                      hdcf, hdca, primary_points, team_abbrevs="HOM"):
    conn.execute("""
        INSERT INTO player_season_advanced_stats
            (player_id, season_id, game_type, team_abbrevs, strength_state,
             cf, ca, ff, fa, hdcf, hdca, gf, ga, primary_points, toi_seconds, gp)
        VALUES (?, ?, 2, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, ?, 900, 20)
    """, (player_id, season_id, team_abbrevs, strength_state, cf, ca, ff, fa,
          hdcf, hdca, primary_points))
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
