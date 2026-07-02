"""
Query examples — uncomment one block at a time and run this script.
Each example builds on the previous one and teaches a new SQL concept.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.database import get_connection

conn = get_connection()


# ─────────────────────────────────────────────
# EXAMPLE 1: Simple SELECT — list all teams
# Concept: basic SELECT, column aliases
# ─────────────────────────────────────────────
print("=== Example 1: All Teams ===")
rows = conn.execute("SELECT abbrev, place_name, common_name, division FROM teams ORDER BY division, abbrev").fetchall()
for r in rows:
    print(f"  {r['abbrev']:4}  {r['place_name']:20} {r['common_name']:15} {r['division']}")


# ─────────────────────────────────────────────
# EXAMPLE 2: WHERE filter — one division
# Concept: filtering rows
# ─────────────────────────────────────────────
print("\n=== Example 2: Metropolitan Division ===")
rows = conn.execute(
    "SELECT abbrev, place_name, common_name FROM teams WHERE division = 'Metropolitan' ORDER BY abbrev"
).fetchall()
for r in rows:
    print(f"  {r['abbrev']:4}  {r['place_name']}")


# ─────────────────────────────────────────────
# EXAMPLE 3: ORDER BY + LIMIT — top 10 by points
# Concept: sorting and limiting results
# ─────────────────────────────────────────────
print("\n=== Example 3: Top 10 Teams by Points (latest standings) ===")
rows = conn.execute("""
    SELECT t.abbrev, t.common_name, s.points, s.wins, s.losses, s.ot_losses
    FROM standings s
    JOIN teams t ON s.team_id = t.team_id
    WHERE s.snapshot_date = (SELECT MAX(snapshot_date) FROM standings)
    ORDER BY s.points DESC, s.regulation_wins DESC
    LIMIT 10
""").fetchall()
for i, r in enumerate(rows, 1):
    print(f"  {i:2}. {r['abbrev']:4}  {r['common_name']:20}  {r['points']} pts  ({r['wins']}-{r['losses']}-{r['ot_losses']})")


# ─────────────────────────────────────────────
# EXAMPLE 4: JOIN — players with their team name
# Concept: joining two tables
# ─────────────────────────────────────────────
print("\n=== Example 4: Players on the Carolina Hurricanes ===")
rows = conn.execute("""
    SELECT p.first_name, p.last_name, p.position_code, p.sweater_number
    FROM players p
    JOIN teams t ON p.current_team_id = t.team_id
    WHERE t.abbrev = 'CAR'
    ORDER BY p.position_code, p.sweater_number
""").fetchall()
for r in rows:
    print(f"  #{r['sweater_number']:2}  {r['position_code']}  {r['first_name']} {r['last_name']}")


# ─────────────────────────────────────────────
# EXAMPLE 5: GROUP BY + aggregate — goals per team
# Concept: aggregation with SUM and GROUP BY
# ─────────────────────────────────────────────
print("\n=== Example 5: Goals Scored Per Team (all games) ===")
rows = conn.execute("""
    SELECT t.abbrev, t.common_name, SUM(pgs.goals) AS total_goals
    FROM player_game_stats pgs
    JOIN players p ON pgs.player_id = p.player_id
    JOIN teams t ON pgs.team_id = t.team_id
    GROUP BY pgs.team_id
    ORDER BY total_goals DESC
""").fetchall()
for r in rows:
    print(f"  {r['abbrev']:4}  {r['common_name']:20}  {r['total_goals']} goals")


# ─────────────────────────────────────────────
# EXAMPLE 6: Multi-table JOIN — top 10 goal scorers
# Concept: chaining JOINs, leaderboard query
# ─────────────────────────────────────────────
print("\n=== Example 6: Top 10 Goal Scorers ===")
rows = conn.execute("""
    SELECT p.first_name, p.last_name, t.abbrev, SUM(pgs.goals) AS goals, SUM(pgs.assists) AS assists,
           SUM(pgs.goals) + SUM(pgs.assists) AS points
    FROM player_game_stats pgs
    JOIN players p ON pgs.player_id = p.player_id
    JOIN teams t ON p.current_team_id = t.team_id
    GROUP BY pgs.player_id
    ORDER BY goals DESC, points DESC
    LIMIT 10
""").fetchall()
for i, r in enumerate(rows, 1):
    print(f"  {i:2}. {r['first_name']} {r['last_name']:20} ({r['abbrev']})  {r['goals']}G {r['assists']}A {r['points']}PTS")


conn.close()
