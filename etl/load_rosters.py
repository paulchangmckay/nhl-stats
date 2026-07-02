import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import api_client, database
from src.models import Player


def _parse_player(p, team_id):
    return Player(
        player_id=p["id"],
        first_name=p["firstName"]["default"],
        last_name=p["lastName"]["default"],
        position_code=p.get("positionCode"),
        sweater_number=p.get("sweaterNumber"),
        shoots_catches=p.get("shootsCatches"),
        height_inches=p.get("heightInInches"),
        weight_pounds=p.get("weightInPounds"),
        birth_date=p.get("birthDate"),
        birth_country=p.get("birthCountry"),
        current_team_id=team_id,
        birth_city=p.get("birthCity", {}).get("default") if isinstance(p.get("birthCity"), dict) else p.get("birthCity"),
        birth_state_province=p.get("birthStateProvince", {}).get("default") if isinstance(p.get("birthStateProvince"), dict) else p.get("birthStateProvince"),
        headshot_url=p.get("headshot"),
    )


def run(conn):
    print("Loading rosters (one API call per team)...")
    teams = conn.execute("SELECT team_id, abbrev FROM teams").fetchall()
    total = 0

    for team in teams:
        team_id = team["team_id"]
        abbrev = team["abbrev"]
        try:
            roster = api_client.get_roster(abbrev)
            time.sleep(0.5)  # stay under NHL API rate limit
        except Exception as e:
            print(f"  Warning: could not fetch roster for {abbrev}: {e}")
            time.sleep(2)
            continue

        all_players = (
            roster.get("forwards", []) +
            roster.get("defensemen", []) +
            roster.get("goalies", [])
        )

        for p in all_players:
            player = _parse_player(p, team_id)
            database.upsert_player(conn, player.__dict__)
            total += 1

        print(f"  {abbrev}: {len(all_players)} players")

    conn.commit()
    print(f"  {total} players loaded across {len(teams)} teams.")


if __name__ == "__main__":
    conn = database.get_connection()
    run(conn)
    conn.close()
