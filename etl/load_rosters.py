import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import api_client, database
from src.models import Player


def _parse_player(p, team_id, position_code):
    return Player(
        player_id=p["id"],
        first_name=p["firstName"]["default"],
        last_name=p["lastName"]["default"],
        position_code=position_code,
        sweater_number=p.get("sweaterNumber"),
        shoots_catches=p.get("shootsCatches"),
        height_inches=p.get("heightInInches"),
        weight_pounds=p.get("weightInPounds"),
        birth_date=p.get("birthDate"),
        birth_country=p.get("birthCountry"),
        current_team_id=team_id,
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
        except Exception as e:
            print(f"  Warning: could not fetch roster for {abbrev}: {e}")
            continue

        players = (
            [(_parse_player(p, team_id, "F"), ) for p in roster.get("forwards", [])] +
            [(_parse_player(p, team_id, "D"), ) for p in roster.get("defensemen", [])] +
            [(_parse_player(p, team_id, "G"), ) for p in roster.get("goalies", [])]
        )

        for (player,) in players:
            database.upsert_player(conn, player.__dict__)
            total += 1

        print(f"  {abbrev}: {len(players)} players")

    conn.commit()
    print(f"  {total} players loaded across {len(teams)} teams.")


if __name__ == "__main__":
    conn = database.get_connection()
    run(conn)
    conn.close()
