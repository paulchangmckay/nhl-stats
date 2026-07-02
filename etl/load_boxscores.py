import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import api_client, database
from src.models import Player, PlayerGameStats


def _ensure_player(conn, player, team_id):
    """Insert a minimal player record if not already in the DB."""
    existing = conn.execute(
        "SELECT 1 FROM players WHERE player_id = ?", (player["playerId"],)
    ).fetchone()
    if not existing:
        name = player.get("name", {}).get("default", "Unknown")
        parts = name.rsplit(" ", 1)
        first = parts[0] if len(parts) > 1 else name
        last = parts[1] if len(parts) > 1 else ""
        stub = Player(
            player_id=player["playerId"],
            first_name=first,
            last_name=last,
            position_code=player.get("position"),
            sweater_number=player.get("sweaterNumber"),
            shoots_catches=None,
            height_inches=None,
            weight_pounds=None,
            birth_date=None,
            birth_country=None,
            current_team_id=team_id,
        )
        database.upsert_player(conn, stub.__dict__)


def _extract_player_stats(player, game_id, team_id):
    return PlayerGameStats(
        game_id=game_id,
        player_id=player["playerId"],
        team_id=team_id,
        goals=player.get("goals", 0),
        assists=player.get("assists", 0),
        points=player.get("points", 0),
        plus_minus=player.get("plusMinus", 0),
        pim=player.get("pim", 0),
        hits=player.get("hits", 0),
        shots_on_goal=player.get("sog", 0),
        blocked_shots=player.get("blockedShots", 0),
        toi=player.get("toi"),
    )


def run(conn):
    print("Loading boxscores for completed games...")

    pending = conn.execute("""
        SELECT g.game_id FROM games g
        WHERE g.game_state = 'OFF'
          AND NOT EXISTS (
              SELECT 1 FROM player_game_stats pgs WHERE pgs.game_id = g.game_id
          )
    """).fetchall()

    print(f"  {len(pending)} completed games need boxscores.")
    total_stats = 0

    for row in pending:
        game_id = row["game_id"]
        try:
            data = api_client.get_boxscore(game_id)
        except Exception as e:
            print(f"  Warning: could not fetch boxscore for game {game_id}: {e}")
            continue

        home = data.get("homeTeam", {})
        away = data.get("awayTeam", {})
        last_period = data.get("gameOutcome", {}).get("lastPeriodType")
        database.update_game_score(
            conn, game_id,
            home.get("score"), away.get("score"),
            last_period, data.get("gameState"),
        )

        by_team = data.get("playerByGameStats", {})
        for side_key, team_data in [("awayTeam", away), ("homeTeam", home)]:
            team_id = team_data.get("id")
            side = by_team.get(side_key, {})
            for group in ["forwards", "defense", "goalies"]:
                for player in side.get(group, []):
                    _ensure_player(conn, player, team_id)
                    stats = _extract_player_stats(player, game_id, team_id)
                    database.insert_player_game_stats(conn, stats.__dict__)
                    total_stats += 1

    conn.commit()
    print(f"  {total_stats} player-game stat rows inserted.")


if __name__ == "__main__":
    conn = database.get_connection()
    run(conn)
    conn.close()
