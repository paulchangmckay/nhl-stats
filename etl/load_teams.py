import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import api_client, database
from src.models import Team


def run(conn):
    print("Loading teams...")
    standings = api_client.get_standings()
    count = 0
    for row in standings:
        team = Team(
            team_id=row["teamId"],
            abbrev=row["teamAbbrev"]["default"],
            common_name=row["teamName"]["default"],
            place_name=row["teamCommonName"]["default"],
            conference=row.get("conferenceAbbrev"),
            division=row.get("divisionName"),
        )
        database.upsert_team(conn, team.__dict__)
        count += 1
    conn.commit()
    print(f"  {count} teams loaded.")


if __name__ == "__main__":
    conn = database.get_connection()
    run(conn)
    conn.close()
