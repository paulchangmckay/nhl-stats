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


def _seed_event(conn, game_id, event_id, event_owner_team_id=HOME,
                 shooting_player_id=None, shot_type="wrist", x_coord=10, y_coord=0):
    database.insert_game_event(conn, {
        "game_id": game_id, "event_id": event_id, "period": 1,
        "time_in_period": "00:10", "situation_code": "1551",
        "event_type": "shot-on-goal", "zone_code": "O", "x_coord": x_coord,
        "y_coord": y_coord, "shot_type": shot_type, "event_owner_team_id": event_owner_team_id,
        "shooting_player_id": shooting_player_id, "blocking_player_id": None, "goalie_in_net_id": None,
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


def test_run_invokes_season_aggregation_and_percentiles_automatically(conn):
    # Critical bug caught in code review: compute_season_aggregates and
    # compute_percentiles existed and had their own passing unit tests, but
    # nothing in run() (or run_all_etl.py, or the documented __main__ entry
    # point) ever actually called them -- the season/percentile tables would
    # have stayed permanently empty in production. run() must drive both,
    # for every distinct (season_id, game_type) / season_id present, not
    # just process per-game rows.
    for i in range(1, 11):  # 10 games so the 10-GP percentile floor is cleared
        _seed_game(conn, 2024020000 + i)
        _seed_shift(conn, 2024020000 + i, 1, player_id=1, team_id=HOME)
        _seed_event(conn, 2024020000 + i, 1)
    conn.commit()

    module.run(conn)

    season_row = conn.execute("""
        SELECT cf FROM player_season_advanced_stats
        WHERE player_id = 1 AND season_id = '20242025' AND game_type = 2 AND strength_state = '5v5'
    """).fetchone()
    assert season_row is not None
    assert season_row["cf"] == 10

    pctile_row = conn.execute(
        "SELECT cf_pct_pctile FROM player_advanced_percentiles WHERE player_id = 1"
    ).fetchone()
    assert pctile_row is not None


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


def test_compute_season_aggregates_scopes_team_abbrevs_to_the_season(conn):
    # Bug caught in code review: the team_abbrevs correlated subquery only
    # filtered by player_id, so a player who appeared for a different team in
    # a DIFFERENT season would have that other season's team abbreviation
    # bleed into this season's row -- and that wrong value feeds directly
    # into the PDO lookup in app.py.
    OTHER_TEAM = 3
    database.upsert_team(conn, {"team_id": OTHER_TEAM, "abbrev": "OTH", "common_name": "Other",
                                 "place_name": "Other", "conference": None, "division": None})

    _seed_game(conn, 2024020001, season_id="20242025")
    _seed_shift(conn, 2024020001, 1, player_id=1, team_id=HOME)
    _seed_event(conn, 2024020001, 1)

    _seed_game(conn, 2023020001, season_id="20232024")
    database.insert_player_shift(conn, {
        "game_id": 2023020001, "shift_id": 1, "player_id": 1, "team_id": OTHER_TEAM,
        "period": 1, "start_time": "00:00", "end_time": "20:00", "duration": "20:00",
    })
    _seed_event(conn, 2023020001, 1, event_owner_team_id=OTHER_TEAM)
    conn.commit()

    module.run(conn)
    module.compute_season_aggregates(conn, season_id="20242025", game_type=2)

    row = conn.execute("""
        SELECT team_abbrevs FROM player_season_advanced_stats
        WHERE player_id = 1 AND season_id = '20242025' AND game_type = 2 AND strength_state = '5v5'
    """).fetchone()
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


def test_schema_has_new_rate_stat_columns_and_zscore_table(conn):
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(player_game_advanced_stats)")}
    assert {"icf", "ihdcf", "rebounds_created", "deflections", "points"} <= cols

    season_cols = {row["name"] for row in conn.execute("PRAGMA table_info(player_season_advanced_stats)")}
    assert {"icf", "ihdcf", "rebounds_created", "deflections", "points"} <= season_cols

    career_cols = {row["name"] for row in conn.execute("PRAGMA table_info(player_career_advanced_stats)")}
    assert {"rs_icf", "rs_ihdcf", "rs_rebounds_created", "rs_deflections", "rs_points",
            "po_icf", "po_ihdcf", "po_rebounds_created", "po_deflections", "po_points"} <= career_cols

    zscore_cols = {row["name"] for row in conn.execute("PRAGMA table_info(player_rate_zscores)")}
    assert {"season_id", "player_id", "position_group", "shots_per60_z", "chances_per60_z",
            "rebounds_created_per60_z", "deflections_per60_z", "points_per60_z",
            "primary_points_per60_z"} <= zscore_cols


def test_compute_season_aggregates_sums_new_rate_stat_columns(conn):
    _seed_game(conn, 2024020001)
    _seed_shift(conn, 2024020001, 1, player_id=1, team_id=HOME)
    _seed_event(conn, 2024020001, 1, shooting_player_id=1, shot_type="deflected")
    conn.commit()

    module.run(conn)

    row = conn.execute("""
        SELECT icf, ihdcf, deflections FROM player_season_advanced_stats
        WHERE player_id = 1 AND season_id = '20242025' AND game_type = 2 AND strength_state = '5v5'
    """).fetchone()
    assert row["icf"] == 1
    assert row["deflections"] == 1


def _seed_zscore_population(conn, count, season_id="20242025", icf_start=1, toi_seconds=3600, game_type=2):
    for player_id in range(1, count + 1):
        database.upsert_player_stub(conn, {
            "player_id": player_id, "first_name": "P", "last_name": str(player_id),
            "position_code": "C", "shoots_catches": None,
        })
        icf = icf_start if icf_start is not None else player_id
        conn.execute("""
            INSERT INTO player_season_advanced_stats
                (player_id, season_id, game_type, team_abbrevs, strength_state,
                 cf, ca, ff, fa, hdcf, hdca, gf, ga, primary_points, toi_seconds, gp,
                 icf, ihdcf, rebounds_created, deflections, points)
            VALUES (?, ?, ?, 'HOM', '5v5', 1,1,1,1,1,1,1,1,1, ?, 12, ?, 3, 1, 1, 5)
        """, (player_id, season_id, game_type, toi_seconds, icf))
    conn.commit()


def test_compute_zscores_below_min_population_yields_no_rows(conn):
    _seed_zscore_population(conn, count=5)
    module.compute_zscores(conn, season_id="20242025")
    row = conn.execute("SELECT * FROM player_rate_zscores WHERE player_id = 1").fetchone()
    assert row is None


def test_compute_zscores_computes_expected_values_for_qualifying_population(conn):
    for player_id in range(1, 21):
        database.upsert_player_stub(conn, {
            "player_id": player_id, "first_name": "P", "last_name": str(player_id),
            "position_code": "C", "shoots_catches": None,
        })
        conn.execute("""
            INSERT INTO player_season_advanced_stats
                (player_id, season_id, game_type, team_abbrevs, strength_state,
                 cf, ca, ff, fa, hdcf, hdca, gf, ga, primary_points, toi_seconds, gp,
                 icf, ihdcf, rebounds_created, deflections, points)
            VALUES (?, '20242025', 2, 'HOM', '5v5', 1,1,1,1,1,1,1,1,1, 3600, 12, ?, 3, 1, 1, 5)
        """, (player_id, player_id))
    conn.commit()

    module.compute_zscores(conn, season_id="20242025")

    import statistics
    rates = list(range(1, 21))  # toi_seconds=3600 (1hr) -> rate == icf directly
    mean = statistics.mean(rates)
    stdev = statistics.pstdev(rates)
    expected = round((1 - mean) / stdev, 2)

    row = conn.execute("SELECT shots_per60_z FROM player_rate_zscores WHERE player_id = 1").fetchone()
    assert row["shots_per60_z"] == expected


def test_compute_zscores_zero_stddev_population_yields_zero(conn):
    _seed_zscore_population(conn, count=20, icf_start=10)  # identical icf for everyone
    module.compute_zscores(conn, season_id="20242025")
    row = conn.execute("SELECT shots_per60_z FROM player_rate_zscores WHERE player_id = 1").fetchone()
    assert row["shots_per60_z"] == 0.0


def test_compute_zscores_excludes_zero_toi_player(conn):
    for player_id in range(1, 21):
        database.upsert_player_stub(conn, {
            "player_id": player_id, "first_name": "P", "last_name": str(player_id),
            "position_code": "C", "shoots_catches": None,
        })
        toi = 0 if player_id == 1 else 3600
        conn.execute("""
            INSERT INTO player_season_advanced_stats
                (player_id, season_id, game_type, team_abbrevs, strength_state,
                 cf, ca, ff, fa, hdcf, hdca, gf, ga, primary_points, toi_seconds, gp,
                 icf, ihdcf, rebounds_created, deflections, points)
            VALUES (?, '20242025', 2, 'HOM', '5v5', 1,1,1,1,1,1,1,1,1, ?, 12, 10, 3, 1, 1, 5)
        """, (player_id, toi))
    conn.commit()

    module.compute_zscores(conn, season_id="20242025")
    row = conn.execute("SELECT * FROM player_rate_zscores WHERE player_id = 1").fetchone()
    assert row is None


def test_compute_zscores_filters_by_game_type_regular_season_only(conn):
    _seed_zscore_population(conn, count=20)
    database.upsert_player_stub(conn, {
        "player_id": 21, "first_name": "P", "last_name": "21",
        "position_code": "C", "shoots_catches": None,
    })
    conn.execute("""
        INSERT INTO player_season_advanced_stats
            (player_id, season_id, game_type, team_abbrevs, strength_state,
             cf, ca, ff, fa, hdcf, hdca, gf, ga, primary_points, toi_seconds, gp,
             icf, ihdcf, rebounds_created, deflections, points)
        VALUES (21, '20242025', 3, 'HOM', '5v5', 1,1,1,1,1,1,1,1,1, 3600, 12, 999, 3, 1, 1, 5)
    """)
    conn.commit()

    module.compute_zscores(conn, season_id="20242025")
    row = conn.execute("SELECT * FROM player_rate_zscores WHERE player_id = 21").fetchone()
    assert row is None


def test_compute_percentiles_hdcf_pctile_null_when_hdcf_null_excluded_from_population(conn):
    # 20 players with real HD data (meets the min-population floor for a
    # meaningful ranking); player 21's season HD data is NULL (e.g. a
    # 2017-18/2018-19 season with zero rink-side coverage all year) and must
    # not affect anyone else's ranking.
    for player_id in range(1, 21):
        database.upsert_player_stub(conn, {
            "player_id": player_id, "first_name": "P", "last_name": str(player_id),
            "position_code": "C", "shoots_catches": None,
        })
        conn.execute("""
            INSERT INTO player_season_advanced_stats
                (player_id, season_id, game_type, team_abbrevs, strength_state,
                 cf, ca, ff, fa, hdcf, hdca, gf, ga, primary_points, toi_seconds, gp)
            VALUES (?, '20172018', 2, 'HOM', '5v5', 20, 10, 20, 10, ?, 1, 1, 1, 1, 900, 12)
        """, (player_id, player_id))  # distinct hdcf per player -- unambiguous ranking
    database.upsert_player_stub(conn, {
        "player_id": 21, "first_name": "P", "last_name": "21",
        "position_code": "C", "shoots_catches": None,
    })
    conn.execute("""
        INSERT INTO player_season_advanced_stats
            (player_id, season_id, game_type, team_abbrevs, strength_state,
             cf, ca, ff, fa, hdcf, hdca, gf, ga, primary_points, toi_seconds, gp)
        VALUES (21, '20172018', 2, 'HOM', '5v5', 20, 10, 20, 10, NULL, NULL, 1, 1, 1, 900, 12)
    """)
    conn.commit()

    module.compute_percentiles(conn, season_id="20172018")

    top = conn.execute(
        "SELECT hdcf_pct_pctile FROM player_advanced_percentiles WHERE player_id = 20"
    ).fetchone()
    null_player = conn.execute(
        "SELECT hdcf_pct_pctile FROM player_advanced_percentiles WHERE player_id = 21"
    ).fetchone()
    assert top["hdcf_pct_pctile"] == 100.0  # ranked against the 20-player real-HD population
    assert null_player["hdcf_pct_pctile"] is None


def test_compute_percentiles_hdcf_pctile_null_for_everyone_when_hd_population_below_floor(conn):
    # 25 players total (well above PERCENTILE_MIN_GP), but only 2 have real HD
    # data -- too few to rank meaningfully. hdcf_pct_pctile must be None for
    # EVERYONE in this group, including the 2 with real data, not just the 23
    # who are NULL. cf_pct_pctile (unrelated to HD) must still compute normally.
    for player_id in range(1, 26):
        database.upsert_player_stub(conn, {
            "player_id": player_id, "first_name": "P", "last_name": str(player_id),
            "position_code": "C", "shoots_catches": None,
        })
        hdcf, hdca = (8, 2) if player_id <= 2 else (None, None)
        conn.execute("""
            INSERT INTO player_season_advanced_stats
                (player_id, season_id, game_type, team_abbrevs, strength_state,
                 cf, ca, ff, fa, hdcf, hdca, gf, ga, primary_points, toi_seconds, gp)
            VALUES (?, '20172018', 2, 'HOM', '5v5', ?, 10, 20, 10, ?, ?, 1, 1, 1, 900, 12)
        """, (player_id, player_id, hdcf, hdca))
    conn.commit()

    module.compute_percentiles(conn, season_id="20172018")

    real_hd_player = conn.execute(
        "SELECT hdcf_pct_pctile, cf_pct_pctile FROM player_advanced_percentiles WHERE player_id = 1"
    ).fetchone()
    assert real_hd_player["hdcf_pct_pctile"] is None  # only 2 real-HD players -- below the floor
    assert real_hd_player["cf_pct_pctile"] is not None  # unrelated to HD, computes normally


def test_compute_percentiles_all_null_hd_season_does_not_crash(conn):
    # Realistic 2017-18/2018-19 shape: EVERY qualifying player's hdcf/hdca is
    # NULL, not just some. Must not crash, and cf_pct_pctile (unrelated to HD)
    # must still compute normally for everyone.
    for player_id in range(1, 4):
        database.upsert_player_stub(conn, {
            "player_id": player_id, "first_name": "P", "last_name": str(player_id),
            "position_code": "C", "shoots_catches": None,
        })
        conn.execute("""
            INSERT INTO player_season_advanced_stats
                (player_id, season_id, game_type, team_abbrevs, strength_state,
                 cf, ca, ff, fa, hdcf, hdca, gf, ga, primary_points, toi_seconds, gp)
            VALUES (?, '20172018', 2, 'HOM', '5v5', ?, 10, 20, 10, NULL, NULL, 1, 1, 1, 900, 12)
        """, (player_id, player_id * 10))
    conn.commit()

    module.compute_percentiles(conn, season_id="20172018")

    row = conn.execute(
        "SELECT hdcf_pct_pctile, cf_pct_pctile FROM player_advanced_percentiles WHERE player_id = 1"
    ).fetchone()
    assert row["hdcf_pct_pctile"] is None
    assert row["cf_pct_pctile"] is not None


def test_compute_zscores_chances_per60_z_null_when_ihdcf_null(conn):
    # 20 qualifying players (meets ZSCORE_MIN_POPULATION); player 1's ihdcf
    # is NULL (e.g. a fully rink-side-missing season) while everyone else's
    # is real -- player 1 should get chances_per60_z = NULL but a normal
    # shots_per60_z (icf-based, unaffected by the HD-only NULL).
    for player_id in range(1, 21):
        database.upsert_player_stub(conn, {
            "player_id": player_id, "first_name": "P", "last_name": str(player_id),
            "position_code": "C", "shoots_catches": None,
        })
        ihdcf = "NULL" if player_id == 1 else str(player_id)
        conn.execute(f"""
            INSERT INTO player_season_advanced_stats
                (player_id, season_id, game_type, team_abbrevs, strength_state,
                 cf, ca, ff, fa, hdcf, hdca, gf, ga, primary_points, toi_seconds, gp,
                 icf, ihdcf, rebounds_created, deflections, points)
            VALUES (?, '20172018', 2, 'HOM', '5v5', 1,1,1,1,1,1,1,1,1, 3600, 12,
                    ?, {ihdcf}, 1, 1, 5)
        """, (player_id, player_id))
    conn.commit()

    module.compute_zscores(conn, season_id="20172018")

    p1 = conn.execute(
        "SELECT chances_per60_z, shots_per60_z FROM player_rate_zscores WHERE player_id = 1"
    ).fetchone()
    assert p1["chances_per60_z"] is None
    assert p1["shots_per60_z"] is not None  # icf-based, unaffected


def test_compute_zscores_chances_per60_z_null_for_everyone_when_hd_population_below_floor(conn):
    # 20 qualifying players (meets ZSCORE_MIN_POPULATION overall), but only 2
    # have real ihdcf -- too few to compute a meaningful chances_per60_z. Must
    # be None for EVERYONE in the group, including those 2, while
    # shots_per60_z (icf-based, unaffected) still computes normally for all.
    for player_id in range(1, 21):
        database.upsert_player_stub(conn, {
            "player_id": player_id, "first_name": "P", "last_name": str(player_id),
            "position_code": "C", "shoots_catches": None,
        })
        ihdcf = str(player_id) if player_id <= 2 else "NULL"
        conn.execute(f"""
            INSERT INTO player_season_advanced_stats
                (player_id, season_id, game_type, team_abbrevs, strength_state,
                 cf, ca, ff, fa, hdcf, hdca, gf, ga, primary_points, toi_seconds, gp,
                 icf, ihdcf, rebounds_created, deflections, points)
            VALUES (?, '20172018', 2, 'HOM', '5v5', 1,1,1,1,1,1,1,1,1, 3600, 12,
                    ?, {ihdcf}, 1, 1, 5)
        """, (player_id, player_id))
    conn.commit()

    module.compute_zscores(conn, season_id="20172018")

    real_ihdcf_player = conn.execute(
        "SELECT chances_per60_z, shots_per60_z FROM player_rate_zscores WHERE player_id = 1"
    ).fetchone()
    assert real_ihdcf_player["chances_per60_z"] is None  # only 2 real-ihdcf players -- below the floor
    assert real_ihdcf_player["shots_per60_z"] is not None  # icf-based, unaffected


def test_compute_zscores_all_null_ihdcf_season_does_not_crash(conn):
    # Realistic 2017-18/2018-19 shape: EVERY qualifying player's ihdcf is NULL.
    # Must not crash (empty population, _zscore never called for this metric),
    # and the other 5 rate z-scores must still compute normally.
    for player_id in range(1, 21):
        database.upsert_player_stub(conn, {
            "player_id": player_id, "first_name": "P", "last_name": str(player_id),
            "position_code": "C", "shoots_catches": None,
        })
        conn.execute("""
            INSERT INTO player_season_advanced_stats
                (player_id, season_id, game_type, team_abbrevs, strength_state,
                 cf, ca, ff, fa, hdcf, hdca, gf, ga, primary_points, toi_seconds, gp,
                 icf, ihdcf, rebounds_created, deflections, points)
            VALUES (?, '20172018', 2, 'HOM', '5v5', 1,1,1,1,1,1,1,1,1, 3600, 12,
                    ?, NULL, 1, 1, 5)
        """, (player_id, player_id))
    conn.commit()

    module.compute_zscores(conn, season_id="20172018")

    row = conn.execute(
        "SELECT chances_per60_z, shots_per60_z FROM player_rate_zscores WHERE player_id = 1"
    ).fetchone()
    assert row["chances_per60_z"] is None
    assert row["shots_per60_z"] is not None
