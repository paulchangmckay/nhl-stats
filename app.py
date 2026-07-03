import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, jsonify, render_template, request
from src.database import get_connection

app = Flask(__name__)


def _toi_str(val):
    """Convert decimal seconds '1379.12' or 'MM:SS' string to display 'MM:SS'."""
    if val is None:
        return ""
    try:
        secs = float(val)
        return f"{int(secs // 60)}:{int(secs % 60):02d}"
    except (ValueError, TypeError):
        return str(val)


def _height_str(inches):
    if inches is None:
        return ""
    feet = inches // 12
    remaining = inches % 12
    return f"{feet}'{remaining}\""


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/teams")
def api_teams():
    conn = get_connection()
    rows = conn.execute(
        "SELECT abbrev, common_name FROM teams ORDER BY common_name"
    ).fetchall()
    conn.close()
    return jsonify([{"abbrev": r["abbrev"], "common_name": r["common_name"]} for r in rows])


@app.route("/api/players")
def api_players():
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            p.player_id,
            p.sweater_number,
            p.first_name,
            p.last_name,
            p.position_code,
            p.shoots_catches,
            p.height_inches,
            p.weight_pounds,
            p.birth_date,
            p.birth_country,
            t.abbrev      AS team_abbrev,
            t.common_name AS team_name
        FROM players p
        LEFT JOIN teams t ON p.current_team_id = t.team_id
        ORDER BY p.last_name, p.first_name
    """).fetchall()
    conn.close()

    players = []
    for r in rows:
        players.append({
            "player_id":      r["player_id"],
            "sweater_number": r["sweater_number"],
            "first_name":     r["first_name"],
            "last_name":      r["last_name"],
            "position_code":  r["position_code"] or "",
            "shoots_catches": r["shoots_catches"] or "",
            "height":         _height_str(r["height_inches"]),
            "weight_pounds":  r["weight_pounds"],
            "birth_date":     r["birth_date"] or "",
            "birth_country":  r["birth_country"] or "",
            "team_abbrev":    r["team_abbrev"] or "",
            "team_name":      r["team_name"] or "",
        })
    return jsonify(players)


@app.route("/api/players/stats")
def api_players_stats():
    season = request.args.get("season", "all")
    conn = get_connection()

    if season == "all":
        rows = conn.execute("""
            SELECT
                p.player_id,
                p.first_name,
                p.last_name,
                p.position_code,
                t.abbrev      AS team_abbrev,
                t.common_name AS team_name,
                COALESCE(c.rs_gp, 0) + COALESCE(c.po_gp, 0)               AS gp,
                COALESCE(c.rs_goals, 0) + COALESCE(c.po_goals, 0)         AS goals,
                COALESCE(c.rs_assists, 0) + COALESCE(c.po_assists, 0)     AS assists,
                COALESCE(c.rs_points, 0) + COALESCE(c.po_points, 0)       AS points,
                COALESCE(c.rs_plus_minus, 0) + COALESCE(c.po_plus_minus, 0) AS plus_minus,
                COALESCE(c.rs_pim, 0) + COALESCE(c.po_pim, 0)             AS pim,
                COALESCE(c.rs_pp_goals, 0) + COALESCE(c.po_pp_goals, 0)   AS pp_goals,
                COALESCE(c.rs_sh_goals, 0) + COALESCE(c.po_sh_goals, 0)   AS sh_goals,
                COALESCE(c.rs_shots, 0) + COALESCE(c.po_shots, 0)         AS shots,
                ROUND(
                    (COALESCE(c.rs_goals,0)+COALESCE(c.po_goals,0)) * 100.0
                    / NULLIF(COALESCE(c.rs_shots,0)+COALESCE(c.po_shots,0), 0), 1
                )                                                            AS shooting_pct,
                c.rs_avg_toi                                                AS avg_toi,
                COALESCE(c.rs_wins, 0) + COALESCE(c.po_wins, 0)           AS wins,
                COALESCE(c.rs_losses, 0) + COALESCE(c.po_losses, 0)       AS losses,
                NULL                                                         AS ot_losses,
                COALESCE(c.rs_shutouts, 0) + COALESCE(c.po_shutouts, 0)   AS shutouts,
                c.rs_save_pct                                               AS save_pct,
                c.rs_gaa                                                    AS gaa
            FROM players p
            LEFT JOIN teams t ON p.current_team_id = t.team_id
            JOIN player_career_stats c ON p.player_id = c.player_id
            ORDER BY points DESC
        """).fetchall()
    else:
        rows = conn.execute("""
            SELECT
                p.player_id,
                p.first_name,
                p.last_name,
                p.position_code,
                t.abbrev      AS team_abbrev,
                t.common_name AS team_name,
                SUM(s.gp)                                                    AS gp,
                SUM(s.goals)                                                 AS goals,
                SUM(s.assists)                                               AS assists,
                SUM(s.points)                                                AS points,
                SUM(s.plus_minus)                                            AS plus_minus,
                SUM(s.pim)                                                   AS pim,
                SUM(s.pp_goals)                                              AS pp_goals,
                SUM(s.sh_goals)                                              AS sh_goals,
                SUM(s.shots)                                                 AS shots,
                ROUND(SUM(s.goals)*100.0 / NULLIF(SUM(s.shots), 0), 1)     AS shooting_pct,
                MAX(CASE WHEN s.game_type = 2 THEN s.avg_toi END)           AS avg_toi,
                SUM(s.wins)                                                  AS wins,
                SUM(s.losses)                                                AS losses,
                SUM(s.ot_losses)                                             AS ot_losses,
                SUM(s.shutouts)                                              AS shutouts,
                MAX(CASE WHEN s.game_type = 2 THEN s.save_pct END)          AS save_pct,
                MAX(CASE WHEN s.game_type = 2 THEN s.gaa END)               AS gaa
            FROM players p
            LEFT JOIN teams t ON p.current_team_id = t.team_id
            JOIN player_season_stats s ON p.player_id = s.player_id
            WHERE s.season_id = ?
            GROUP BY p.player_id
            ORDER BY SUM(s.points) DESC
        """, (season,)).fetchall()

    conn.close()
    players = []
    for r in rows:
        players.append({
            "player_id":    r["player_id"],
            "first_name":   r["first_name"],
            "last_name":    r["last_name"],
            "position_code": r["position_code"] or "",
            "team_abbrev":  r["team_abbrev"] or "",
            "team_name":    r["team_name"] or "",
            "gp":           r["gp"],
            "goals":        r["goals"],
            "assists":      r["assists"],
            "points":       r["points"],
            "plus_minus":   r["plus_minus"],
            "pim":          r["pim"],
            "pp_goals":     r["pp_goals"],
            "sh_goals":     r["sh_goals"],
            "shots":        r["shots"],
            "shooting_pct": r["shooting_pct"],
            "avg_toi":      _toi_str(r["avg_toi"]),
            "wins":         r["wins"],
            "losses":       r["losses"],
            "ot_losses":    r["ot_losses"],
            "shutouts":     r["shutouts"],
            "save_pct":     r["save_pct"],
            "gaa":          r["gaa"],
        })
    return jsonify(players)


if __name__ == "__main__":
    app.run(debug=True)
