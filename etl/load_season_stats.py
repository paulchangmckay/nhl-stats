import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import api_client, database

SEASONS = [
    "20202021",
    "20212022",
    "20222023",
    "20232024",
    "20242025",
    "20252026",
]

GAME_TYPES = {2: "Regular Season", 3: "Playoffs"}


def _parse_name(full_name, last_name):
    """Split full name into first + last. Uses last_name field to find the split point."""
    full_name = full_name.strip()
    if last_name and full_name.endswith(last_name):
        first = full_name[: -(len(last_name))].strip()
        return first or full_name, last_name
    parts = full_name.rsplit(" ", 1)
    return (parts[0], parts[1]) if len(parts) == 2 else (full_name, "")


def _load_player_type(conn, season_id, game_type, player_type):
    """Page through stats REST API for one season/game_type/player_type combo."""
    is_goalie = player_type == "goalie"
    start = 0
    limit = 100
    total_loaded = 0

    while True:
        try:
            resp = api_client.get_season_stats(season_id, game_type, player_type, limit, start)
        except Exception as e:
            print(f"    Warning: API error at start={start}: {e}")
            break

        rows = resp.get("data", [])
        total = resp.get("total", 0)

        for row in rows:
            player_id = row.get("playerId")
            if not player_id:
                continue

            # ── Ensure player stub exists ──────────────────────────────────
            last_name = row.get("lastName", "")
            full_name = row.get("goalieFullName" if is_goalie else "skaterFullName", "")
            first_name, last_name = _parse_name(full_name, last_name)

            database.upsert_player_stub(conn, {
                "player_id":     player_id,
                "first_name":    first_name,
                "last_name":     last_name,
                "position_code": row.get("positionCode"),
                "shoots_catches": row.get("shootsCatches"),
            })

            # ── Upsert season stats row ────────────────────────────────────
            if is_goalie:
                database.upsert_season_stats(conn, {
                    "player_id":    player_id,
                    "season_id":    season_id,
                    "game_type":    game_type,
                    "team_abbrevs": row.get("teamAbbrevs"),
                    "position_code": "G",
                    "gp":      row.get("gamesPlayed"),
                    "wins":    row.get("wins"),
                    "losses":  row.get("losses"),
                    "ot_losses": row.get("otLosses"),
                    "save_pct": row.get("savePct"),
                    "gaa":     row.get("goalsAgainstAverage"),
                    "shutouts": row.get("shutouts"),
                })
            else:
                database.upsert_season_stats(conn, {
                    "player_id":    player_id,
                    "season_id":    season_id,
                    "game_type":    game_type,
                    "team_abbrevs": row.get("teamAbbrevs"),
                    "position_code": row.get("positionCode"),
                    "gp":           row.get("gamesPlayed"),
                    "goals":        row.get("goals"),
                    "assists":      row.get("assists"),
                    "points":       row.get("points"),
                    "plus_minus":   row.get("plusMinus"),
                    "pim":          row.get("penaltyMinutes"),
                    "pp_goals":     row.get("ppGoals"),
                    "sh_goals":     row.get("shGoals"),
                    "shots":        row.get("shots"),
                    "shooting_pct": row.get("shootingPct"),
                    "avg_toi":      row.get("timeOnIcePerGame"),
                })

        total_loaded += len(rows)
        conn.commit()

        if total_loaded >= total or not rows:
            break

        start += limit
        time.sleep(0.2)

    return total_loaded


def _parse_toi_seconds(toi):
    if not toi:
        return 0
    minutes, _, seconds = toi.partition(":")
    try:
        return int(minutes) * 60 + int(seconds)
    except ValueError:
        return 0


def _format_toi_seconds(total_seconds):
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


def _fill_missing_skater_season_stats(conn, season_id, game_type):
    """Aggregate a season-stats row directly from player_game_stats for any
    skater who has games this season/game_type but never showed up in the
    bulk stats REST API response (e.g. fringe players with very few games
    that the leaderboard endpoint excludes). Goalies are skipped on purpose:
    player_game_stats never captures goaltending-specific stats (saves,
    shots-against, decision), so there is nothing accurate to aggregate for
    them yet -- see GitHub issue #84."""
    candidates = conn.execute("""
        SELECT DISTINCT pgs.player_id
        FROM player_game_stats pgs
        JOIN games g ON g.game_id = pgs.game_id
        JOIN players p ON p.player_id = pgs.player_id
        WHERE g.season_id = ? AND g.game_type = ?
          AND COALESCE(p.position_code, '') != 'G'
          AND NOT EXISTS (
              SELECT 1 FROM player_season_stats pss
              WHERE pss.player_id = pgs.player_id
                AND pss.season_id = ? AND pss.game_type = ?
          )
    """, (season_id, game_type, season_id, game_type)).fetchall()

    # wolf-debt: a fallback row, once inserted, is frozen -- the NOT EXISTS check
    # above permanently excludes this player from future fallback runs even if they
    # play more games later in the season and the bulk API still never picks them
    # up. Strictly better than no row at all, but stats will go stale for the rest
    # of the season. Upgrade trigger: if a fringe player accumulates enough games
    # for their frozen fallback numbers to visibly diverge from reality.
    filled = 0
    for row in candidates:
        player_id = row["player_id"]

        games = conn.execute("""
            SELECT pgs.goals, pgs.assists, pgs.points, pgs.plus_minus, pgs.pim,
                   pgs.shots_on_goal, pgs.toi, t.abbrev
            FROM player_game_stats pgs
            JOIN games g ON g.game_id = pgs.game_id
            LEFT JOIN teams t ON t.team_id = pgs.team_id
            WHERE pgs.player_id = ? AND g.season_id = ? AND g.game_type = ?
        """, (player_id, season_id, game_type)).fetchall()

        position_code = conn.execute(
            "SELECT position_code FROM players WHERE player_id = ?", (player_id,)
        ).fetchone()["position_code"]

        gp = len(games)
        goals = sum(g["goals"] or 0 for g in games)
        assists = sum(g["assists"] or 0 for g in games)
        points = sum(g["points"] or 0 for g in games)
        plus_minus = sum(g["plus_minus"] or 0 for g in games)
        pim = sum(g["pim"] or 0 for g in games)
        shots = sum(g["shots_on_goal"] or 0 for g in games)
        total_toi_seconds = sum(_parse_toi_seconds(g["toi"]) for g in games)
        team_abbrevs = ",".join(sorted({g["abbrev"] for g in games if g["abbrev"]}))

        database.upsert_season_stats(conn, {
            "player_id": player_id,
            "season_id": season_id,
            "game_type": game_type,
            "team_abbrevs": team_abbrevs or None,
            "position_code": position_code,
            "gp": gp,
            "goals": goals,
            "assists": assists,
            "points": points,
            "plus_minus": plus_minus,
            "pim": pim,
            "shots": shots,
            "shooting_pct": (goals / shots * 100) if shots else None,
            "avg_toi": _format_toi_seconds(total_toi_seconds // gp) if gp else None,
        })
        filled += 1

    conn.commit()
    return filled


def run(conn):
    print("Loading historical season stats (stats REST API)...")
    grand_total = 0
    current_season = SEASONS[-1]  # always re-fetch the latest season

    for season_id in SEASONS:
        if season_id != current_season:
            synced_at = database.get_sync_record(conn, f"season_stats:{season_id}")
            if synced_at:
                # wolf-debt: the skater fallback below never runs for a season already
                # marked synced here -- a historical season's fringe skaters (issue #83's
                # bug class) only get backfilled if this sync_log row is cleared first
                # (see scripts/sync.py's docstring for the manual re-sync command).
                # Upgrade trigger: if a historical (non-current) season is confirmed to
                # have the same missing-fringe-skater gap as the current season did.
                print(f"  {season_id}: already synced ({synced_at}), skipping")
                continue

        season_total = 0
        for game_type, label in GAME_TYPES.items():
            for player_type in ["skater", "goalie"]:
                n = _load_player_type(conn, season_id, game_type, player_type)
                print(f"  {season_id} {label} {player_type}s: {n}")
                season_total += n
                time.sleep(0.3)

            fallback_n = _fill_missing_skater_season_stats(conn, season_id, game_type)
            if fallback_n:
                print(f"  {season_id} {label} fallback (skaters missing from bulk API): {fallback_n}")
                season_total += fallback_n
        print(f"  Season {season_id} total: {season_total} records")
        grand_total += season_total

        database.set_sync_record(conn, f"season_stats:{season_id}", season_total)

    player_count = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
    print(f"\n  Done. {grand_total} season-stat rows loaded.")
    print(f"  Players in DB now: {player_count}")


if __name__ == "__main__":
    conn = database.get_connection()
    run(conn)
    conn.close()
