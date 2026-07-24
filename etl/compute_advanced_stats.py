import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import database
from etl.advanced_stats.sweep import compute_game_advanced_stats

PERCENTILE_STRENGTH_STATES = ("5v5", "5v4", "4v5")
PERCENTILE_MIN_GP = 10


def run(conn):
    print("Computing advanced stats for completed games...")

    pending = conn.execute("""
        SELECT g.game_id, g.game_type, g.home_team_id FROM games g
        WHERE g.game_state = 'OFF'
          AND NOT EXISTS (
              SELECT 1 FROM player_game_advanced_stats pgas WHERE pgas.game_id = g.game_id
          )
    """).fetchall()

    print(f"  {len(pending)} completed games need advanced stats.")

    for row in pending:
        game_id, game_type, home_team_id = row["game_id"], row["game_type"], row["home_team_id"]
        try:
            shifts = _load_shifts_for_sweep(conn, game_id)
            events = _load_events_for_sweep(conn, game_id)
            player_rows, team_rows = compute_game_advanced_stats(
                shifts, events, home_team_id=home_team_id, game_type=game_type
            )
            for pr in player_rows:
                database.upsert_player_game_advanced_stats(conn, {**pr, "game_id": game_id})
            for tr in team_rows:
                database.upsert_team_game_advanced_stats(conn, {**tr, "game_id": game_id})
            conn.commit()
        except Exception as e:
            print(f"  Warning: could not compute advanced stats for game {game_id}: {e}")

    print("  Advanced stats computation complete.")


def _load_shifts_for_sweep(conn, game_id):
    rows = conn.execute("""
        SELECT ps.player_id, ps.team_id, ps.period, ps.start_time, ps.end_time,
               p.position_code
        FROM player_shifts ps JOIN players p ON p.player_id = ps.player_id
        WHERE ps.game_id = ?
    """, (game_id,)).fetchall()
    return [dict(r) for r in rows]


def _load_events_for_sweep(conn, game_id):
    rows = conn.execute("""
        SELECT event_id, period, time_in_period, situation_code, event_type,
               x_coord, y_coord, event_owner_team_id, shooting_player_id,
               assist1_player_id, home_team_defending_side
        FROM game_events WHERE game_id = ?
    """, (game_id,)).fetchall()
    return [dict(r) for r in rows]


def compute_season_aggregates(conn, season_id, game_type):
    conn.execute("""
        INSERT INTO player_season_advanced_stats
            (player_id, season_id, game_type, team_abbrevs, strength_state,
             cf, ca, ff, fa, hdcf, hdca, gf, ga, primary_points, toi_seconds, gp)
        SELECT
            pgas.player_id, g.season_id, g.game_type,
            (SELECT GROUP_CONCAT(DISTINCT t.abbrev)
             FROM player_game_advanced_stats pgas2
             JOIN teams t ON t.team_id = pgas2.team_id
             WHERE pgas2.player_id = pgas.player_id) AS team_abbrevs,
            pgas.strength_state,
            SUM(pgas.cf), SUM(pgas.ca), SUM(pgas.ff), SUM(pgas.fa),
            SUM(pgas.hdcf), SUM(pgas.hdca), SUM(pgas.gf), SUM(pgas.ga),
            SUM(pgas.primary_points), SUM(pgas.toi_seconds),
            COUNT(DISTINCT pgas.game_id)
        FROM player_game_advanced_stats pgas
        JOIN games g ON g.game_id = pgas.game_id
        WHERE g.season_id = ? AND g.game_type = ?
        GROUP BY pgas.player_id, pgas.strength_state
        ON CONFLICT(player_id, season_id, game_type, strength_state) DO UPDATE SET
            team_abbrevs=excluded.team_abbrevs, cf=excluded.cf, ca=excluded.ca,
            ff=excluded.ff, fa=excluded.fa, hdcf=excluded.hdcf, hdca=excluded.hdca,
            gf=excluded.gf, ga=excluded.ga, primary_points=excluded.primary_points,
            toi_seconds=excluded.toi_seconds, gp=excluded.gp
    """, (season_id, game_type))
    conn.commit()


def compute_percentiles(conn, season_id):
    for strength_state in PERCENTILE_STRENGTH_STATES:
        for position_group, position_codes in (("F", ("C", "L", "R")), ("D", ("D",))):
            placeholders = ",".join("?" * len(position_codes))
            rows = conn.execute(f"""
                SELECT psas.player_id, psas.cf, psas.ca, psas.ff, psas.fa,
                       psas.hdcf, psas.hdca, psas.primary_points
                FROM player_season_advanced_stats psas
                JOIN players p ON p.player_id = psas.player_id
                WHERE psas.season_id = ? AND psas.strength_state = ?
                  AND psas.gp >= ? AND p.position_code IN ({placeholders})
            """, (season_id, strength_state, PERCENTILE_MIN_GP, *position_codes)).fetchall()

            if not rows:
                continue

            def _pct_of(row):
                return row["cf"] / (row["cf"] + row["ca"]) if (row["cf"] + row["ca"]) else 0

            def _fen_pct_of(row):
                return row["ff"] / (row["ff"] + row["fa"]) if (row["ff"] + row["fa"]) else 0

            def _hd_pct_of(row):
                return row["hdcf"] / (row["hdcf"] + row["hdca"]) if (row["hdcf"] + row["hdca"]) else 0

            all_cf_pct = [_pct_of(r) for r in rows]
            all_ff_pct = [_fen_pct_of(r) for r in rows]
            all_hdcf_pct = [_hd_pct_of(r) for r in rows]
            all_pp = [r["primary_points"] for r in rows]

            for r in rows:
                database.upsert_player_advanced_percentiles(conn, {
                    "season_id": season_id, "player_id": r["player_id"],
                    "strength_state": strength_state, "position_group": position_group,
                    "cf_pct_pctile": _percentile_rank(_pct_of(r), all_cf_pct),
                    "ff_pct_pctile": _percentile_rank(_fen_pct_of(r), all_ff_pct),
                    "hdcf_pct_pctile": _percentile_rank(_hd_pct_of(r), all_hdcf_pct),
                    "primary_points_pctile": _percentile_rank(r["primary_points"], all_pp),
                })
    conn.commit()


def _percentile_rank(value, population):
    """Nearest-rank-style percentile: fraction of the population at or below
    this value, scaled to 0-100. A single-player population is defined as
    100 (top of a trivially small group)."""
    if len(population) <= 1:
        return 100.0
    sorted_pop = sorted(population)
    rank = sorted_pop.index(value)
    return (rank / (len(sorted_pop) - 1)) * 100.0


if __name__ == "__main__":
    conn = database.get_connection()
    run(conn)
    conn.close()
