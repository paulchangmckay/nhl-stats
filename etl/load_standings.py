import sys
import os
from datetime import date
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import api_client, database
from src.models import Season, StandingsSnapshot


def _parse_season(season_id_str):
    """Converts '20252026' → Season(season_id, 2025, 2026)."""
    s = str(season_id_str)
    return Season(season_id=s, start_year=int(s[:4]), end_year=int(s[4:]))


def run(conn):
    print("Loading standings...")
    today = date.today().isoformat()
    standings = api_client.get_standings()

    seasons_seen = set()
    count = 0

    for row in standings:
        season_id = str(row.get("seasonId", ""))
        if season_id and season_id not in seasons_seen:
            season = _parse_season(season_id)
            database.upsert_season(conn, season.__dict__)
            seasons_seen.add(season_id)

        streak = row.get("streakCode", "")
        snapshot = StandingsSnapshot(
            snapshot_date=today,
            season_id=season_id or None,
            team_id=row["teamId"],
            games_played=row.get("gamesPlayed", 0),
            wins=row.get("wins", 0),
            losses=row.get("losses", 0),
            ot_losses=row.get("otLosses", 0),
            points=row.get("points", 0),
            regulation_wins=row.get("regulationWins", 0),
            goal_for=row.get("goalFor", 0),
            goal_against=row.get("goalAgainst", 0),
            point_pct=row.get("pointPctg", 0.0),
            streak_code=streak[0] if streak else None,
            streak_count=int(streak[1:]) if len(streak) > 1 else None,
        )
        database.insert_standings_snapshot(conn, snapshot.__dict__)
        count += 1

    conn.commit()
    print(f"  {count} standings rows loaded for {today}.")


if __name__ == "__main__":
    conn = database.get_connection()
    run(conn)
    conn.close()
