"""
Incremental sync — run this for day-to-day updates.

What it does:
  - Rosters: always re-fetches all 32 teams (catches trades/signings/releases)
  - Season stats: skips historical seasons already in sync_log; always re-fetches the latest season
  - Player enrichment: skips retired players already enriched; re-enriches active players
    whose enriched_at is older than 7 days (picks up career total changes)

For a full rebuild from scratch, use run_all_etl.py instead.

To force-resync a specific season:
  sqlite3 data/nhl_stats.db "DELETE FROM sync_log WHERE key='season_stats:20232024';"
  python etl/load_season_stats.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.database import get_connection
from etl import load_rosters, load_season_stats, enrich_players

conn = get_connection()

steps = [
    ("Rosters / Players", load_rosters),
    ("Season Stats (incremental)", load_season_stats),
    ("Player Enrichment (incremental)", enrich_players),
]

for label, module in steps:
    print(f"\n=== {label} ===")
    try:
        module.run(conn)
    except Exception as e:
        print(f"  ERROR in {label}: {e}")

conn.close()
print("\nSync complete.")
