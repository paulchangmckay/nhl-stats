import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, jsonify, render_template
from src.database import get_connection

app = Flask(__name__)


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
        "SELECT abbrev, common_name FROM teams ORDER BY abbrev"
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


if __name__ == "__main__":
    app.run(debug=True)
