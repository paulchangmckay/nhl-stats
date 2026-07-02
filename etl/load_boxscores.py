import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import api_client, database
from src.models import PlayerGameStats


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

    # Only fetch boxscores for games that are finished and have no stats yet
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

        # Update game score
        home = data.get("homeTeam", {})
        away = data.get("awayTeam", {})
        period_type = data.get("periodDescriptor", {}).get("periodType")
        database.update_game_score(
            conn, game_id,
            home.get("score"), away.get("score"),
            period_type, data.get("gameState"),
        )

        # Insert per-player stats
        by_team = data.get("playerByGameStats", {})
        for side_key, team_data in [("awayTeam", away), ("homeTeam", home)]:
            team_id = team_data.get("id")
            side = by_team.get(side_key, {})
            for group in ["forwards", "defense", "goalies"]:
                for player in side.get(group, []):
                    stats = _extract_player_stats(player, game_id, team_id)
                    database.insert_player_game_stats(conn, stats.__dict__)
                    total_stats += 1

    conn.commit()
    print(f"  {total_stats} player-game stat rows inserted.")


if __name__ == "__main__":
    conn = database.get_connection()
    run(conn)
    conn.close()
