import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import api_client, database

REQUEST_DELAY_SECONDS = 0.2


def _extract_shift(game_id, shift):
    return {
        "game_id": game_id,
        "shift_id": shift["id"],
        "player_id": shift["playerId"],
        "team_id": shift.get("teamId"),
        "period": shift.get("period"),
        "start_time": shift.get("startTime"),
        "end_time": shift.get("endTime"),
        "duration": shift.get("duration"),
    }


def run(conn):
    print("Loading shift charts for completed games...")

    pending = conn.execute("""
        SELECT g.game_id FROM games g
        WHERE g.game_state = 'OFF'
          AND NOT EXISTS (
              SELECT 1 FROM player_shifts ps WHERE ps.game_id = g.game_id
          )
    """).fetchall()

    print(f"  {len(pending)} completed games need shift charts.")
    total_shifts = 0

    for row in pending:
        game_id = row["game_id"]
        try:
            shifts = api_client.get_shift_chart(game_id)
        except Exception as e:
            print(f"  Warning: could not fetch shift chart for game {game_id}: {e}")
            continue

        for shift in shifts:
            try:
                database.ensure_player_stub(
                    conn, shift["playerId"],
                    first_name=shift.get("firstName", "Unknown"),
                    last_name=shift.get("lastName", ""),
                )
                team_id = shift.get("teamId")
                if team_id is not None:
                    database.ensure_team_stub(conn, team_id)
                record = _extract_shift(game_id, shift)
                database.insert_player_shift(conn, record)
                total_shifts += 1
            except Exception as e:
                print(f"  Warning: could not insert shift for game {game_id}: {e}")
                continue

        conn.commit()
        time.sleep(REQUEST_DELAY_SECONDS)

    print(f"  {total_shifts} player_shifts rows inserted.")


if __name__ == "__main__":
    conn = database.get_connection()
    run(conn)
    conn.close()
