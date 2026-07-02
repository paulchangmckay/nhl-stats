import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import api_client, database
from src.models import Game


def run(conn):
    print("Loading schedule...")
    game_week = api_client.get_schedule()
    count = 0

    for day in game_week:
        day_date = day.get("date", "")
        for g in day.get("games", []):
            game = Game(
                game_id=g["id"],
                season_id=str(g.get("season", "")),
                game_type=g.get("gameType"),
                game_date=day_date,
                venue=g.get("venue", {}).get("default"),
                home_team_id=g.get("homeTeam", {}).get("id"),
                away_team_id=g.get("awayTeam", {}).get("id"),
                home_score=g.get("homeTeam", {}).get("score"),
                away_score=g.get("awayTeam", {}).get("score"),
                last_period_type=g.get("gameOutcome", {}).get("lastPeriodType"),
                game_state=g.get("gameState"),
            )
            database.insert_game(conn, game.__dict__)
            count += 1

    conn.commit()
    print(f"  {count} games loaded from current week schedule.")


if __name__ == "__main__":
    conn = database.get_connection()
    run(conn)
    conn.close()
