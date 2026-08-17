import app as app_module
from src import database


def _seed_team_and_player(conn, player_id, team_abbrev, position_code, first, last):
    database.upsert_team(conn, {
        "team_id": player_id, "abbrev": team_abbrev, "common_name": team_abbrev,
        "place_name": team_abbrev, "conference": None, "division": None,
    })
    database.upsert_player_stub(conn, {
        "player_id": player_id, "first_name": first, "last_name": last,
        "position_code": position_code, "shoots_catches": None,
    })
    conn.execute(
        "UPDATE players SET current_team_id = ? WHERE player_id = ?",
        (player_id, player_id),
    )


def test_rankings_returns_skaters_and_goalies(conn, monkeypatch):
    _seed_team_and_player(conn, 1, "HOM", "C", "Skater", "One")
    _seed_team_and_player(conn, 2, "HOM", "G", "Goalie", "Two")
    conn.execute("""
        INSERT INTO player_rate_zscores
            (season_id, player_id, position_group, shots_per60_z, chances_per60_z,
             rebounds_created_per60_z, deflections_per60_z, points_per60_z,
             primary_points_per60_z, ca_per60_z, hdca_per60_z)
        VALUES ('20242025', 1, 'F', 0.5, 0.1, 0.2, 0.3, 0.4, 1.2, -0.6, -0.7)
    """)
    conn.execute("""
        INSERT INTO goalie_rate_zscores (season_id, player_id, sv_pct_z, gaa_z)
        VALUES ('20242025', 2, 0.9, -0.4)
    """)
    conn.commit()

    monkeypatch.setattr(app_module, "get_connection", lambda: conn)
    client = app_module.app.test_client()
    resp = client.get("/api/players/rankings?season=20242025")

    assert resp.status_code == 200
    rows = resp.get_json()
    skater = next(r for r in rows if r["player_id"] == 1)
    goalie = next(r for r in rows if r["player_id"] == 2)

    assert skater["position_group"] == "F"
    assert skater["primary_points_per60_z"] == 1.2
    assert skater["ca_per60_z"] == -0.6
    assert skater["sv_pct_z"] is None

    assert goalie["position_group"] == "G"
    assert goalie["sv_pct_z"] == 0.9
    assert goalie["gaa_z"] == -0.4
    assert goalie["primary_points_per60_z"] is None


def test_rankings_team_filter_narrows_to_one_team(conn, monkeypatch):
    _seed_team_and_player(conn, 1, "HOM", "C", "Home", "Player")
    _seed_team_and_player(conn, 2, "AWY", "C", "Away", "Player")
    for pid in (1, 2):
        conn.execute("""
            INSERT INTO player_rate_zscores
                (season_id, player_id, position_group, shots_per60_z, chances_per60_z,
                 rebounds_created_per60_z, deflections_per60_z, points_per60_z,
                 primary_points_per60_z, ca_per60_z, hdca_per60_z)
            VALUES ('20242025', ?, 'F', 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, -0.1, -0.1)
        """, (pid,))
    conn.commit()

    monkeypatch.setattr(app_module, "get_connection", lambda: conn)
    client = app_module.app.test_client()
    resp = client.get("/api/players/rankings?season=20242025&team=HOM")

    rows = resp.get_json()
    assert [r["player_id"] for r in rows] == [1]
