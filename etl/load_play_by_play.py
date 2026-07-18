import sys
import os
import json
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import api_client, database

REQUEST_DELAY_SECONDS = 0.2


def _extract_event(game_id, play):
    details = play.get("details", {}) or {}
    period_desc = play.get("periodDescriptor", {}) or {}
    return {
        "game_id": game_id,
        "event_id": play["eventId"],
        "period": period_desc.get("number"),
        "time_in_period": play.get("timeInPeriod"),
        "situation_code": play.get("situationCode"),
        "event_type": play.get("typeDescKey"),
        "zone_code": details.get("zoneCode"),
        "x_coord": details.get("xCoord"),
        "y_coord": details.get("yCoord"),
        "shot_type": details.get("shotType"),
        "event_owner_team_id": details.get("eventOwnerTeamId"),
        "shooting_player_id": details.get("shootingPlayerId") or details.get("scoringPlayerId"),
        "blocking_player_id": details.get("blockingPlayerId"),
        "goalie_in_net_id": details.get("goalieInNetId"),
        "assist1_player_id": details.get("assist1PlayerId"),
        "assist2_player_id": details.get("assist2PlayerId"),
        "details_json": json.dumps(details),
    }


def _ensure_referenced_players(conn, row):
    for key in ("shooting_player_id", "blocking_player_id", "goalie_in_net_id",
                "assist1_player_id", "assist2_player_id"):
        player_id = row.get(key)
        if player_id is not None:
            database.ensure_player_stub(conn, player_id)


def _ensure_referenced_team(conn, row):
    team_id = row.get("event_owner_team_id")
    if team_id is not None:
        database.ensure_team_stub(conn, team_id)


def run(conn):
    print("Loading play-by-play events for completed games...")

    pending = conn.execute("""
        SELECT g.game_id FROM games g
        WHERE g.game_state = 'OFF'
          AND NOT EXISTS (
              SELECT 1 FROM game_events ge WHERE ge.game_id = g.game_id
          )
    """).fetchall()

    print(f"  {len(pending)} completed games need play-by-play.")
    total_events = 0

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
                _ensure_referenced_players(conn, event)
                _ensure_referenced_team(conn, event)
                database.insert_game_event(conn, event)
                total_events += 1
            except Exception as e:
                print(f"  Warning: could not insert play-by-play event for game {game_id}: {e}")
                continue

        conn.commit()
        time.sleep(REQUEST_DELAY_SECONDS)

    print(f"  {total_events} game_event rows inserted.")


if __name__ == "__main__":
    conn = database.get_connection()
    run(conn)
    conn.close()
