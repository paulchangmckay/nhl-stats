import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import api_client, database
from src.models import Team


def run(conn):
    print("Loading teams...")

    # Get the 32 active teams with conference/division from standings
    standings = api_client.get_standings()
    active = {}
    for row in standings:
        abbrev = row["teamAbbrev"]["default"]
        active[abbrev] = {
            "common_name": row["teamCommonName"]["default"],
            "place_name": row["placeName"]["default"],
            "conference": row.get("conferenceAbbrev"),
            "division": row.get("divisionName"),
        }

    # Get numeric team IDs from the stats REST API, matched by triCode
    all_teams = api_client.get_all_teams()
    id_by_abbrev = {t["triCode"]: t["id"] for t in all_teams}

    count = 0
    for abbrev, info in active.items():
        team_id = id_by_abbrev.get(abbrev)
        if team_id is None:
            print(f"  Warning: no ID found for {abbrev}, skipping.")
            continue
        team = Team(
            team_id=team_id,
            abbrev=abbrev,
            common_name=info["common_name"],
            place_name=info["place_name"],
            conference=info["conference"],
            division=info["division"],
        )
        database.upsert_team(conn, team.__dict__)
        count += 1

    conn.commit()
    print(f"  {count} teams loaded.")


if __name__ == "__main__":
    conn = database.get_connection()
    run(conn)
    conn.close()
