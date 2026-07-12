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


def run(conn):
    print("Loading historical season stats (stats REST API)...")
    grand_total = 0
    current_season = SEASONS[-1]  # always re-fetch the latest season

    for season_id in SEASONS:
        if season_id != current_season:
            synced_at = database.get_sync_record(conn, f"season_stats:{season_id}")
            if synced_at:
                print(f"  {season_id}: already synced ({synced_at}), skipping")
                continue

        season_total = 0
        for game_type, label in GAME_TYPES.items():
            for player_type in ["skater", "goalie"]:
                n = _load_player_type(conn, season_id, game_type, player_type)
                print(f"  {season_id} {label} {player_type}s: {n}")
                season_total += n
                time.sleep(0.3)
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
