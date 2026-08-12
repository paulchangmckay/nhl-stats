import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import api_client, database
from etl.load_play_by_play import _extract_event

REQUEST_DELAY_SECONDS = 0.2


def run(conn):
    print("Backfilling home_team_defending_side for existing games...")

    pending = conn.execute("""
        SELECT DISTINCT g.game_id FROM games g
        JOIN game_events ge ON ge.game_id = g.game_id
        WHERE g.game_state = 'OFF' AND ge.home_team_defending_side IS NULL
    """).fetchall()

    print(f"  {len(pending)} games need defending-side backfill.")
    total_updated = 0

    for row in pending:
        game_id = row["game_id"]
        try:
            data = api_client.get_play_by_play(game_id)
        except Exception as e:
            print(f"  Warning: could not fetch play-by-play for game {game_id}: {e}")
            continue

        for play in data.get("plays", []):
            try:
                event = _extract_event(game_id, play)
                database.insert_game_event(conn, event)  # upsert overwrites the NULL
                total_updated += 1
            except Exception as e:
                print(f"  Warning: could not update event for game {game_id}: {e}")
                continue

        conn.commit()
        time.sleep(REQUEST_DELAY_SECONDS)

    print(f"  {total_updated} game_event rows updated.")


if __name__ == "__main__":
    conn = database.get_connection()
    run(conn)
    conn.close()
