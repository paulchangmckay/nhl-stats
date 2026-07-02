import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.database import get_connection
from etl import load_teams, load_standings, load_rosters, load_schedule, load_boxscores

conn = get_connection()

steps = [
    ("Teams", load_teams),
    ("Standings", load_standings),
    ("Rosters / Players", load_rosters),
    ("Schedule / Games", load_schedule),
    ("Boxscores / Player Stats", load_boxscores),
]

for label, module in steps:
    print(f"\n=== {label} ===")
    try:
        module.run(conn)
    except Exception as e:
        print(f"  ERROR in {label}: {e}")

conn.close()
print("\nAll ETL complete.")
