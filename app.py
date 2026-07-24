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
        """
        SELECT abbrev,
               CASE WHEN place_name LIKE '%' || common_name
                    THEN place_name
                    ELSE place_name || ' ' || common_name
               END AS common_name
        FROM teams
        ORDER BY 2
        """
    ).fetchall()
    conn.close()
    return jsonify([{"abbrev": r["abbrev"], "common_name": r["common_name"]} for r in rows])


def _fetch_players(conn):
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
            t.common_name AS team_name,
            t.place_name  AS team_place_name
        FROM players p
        LEFT JOIN teams t ON p.current_team_id = t.team_id
        ORDER BY p.last_name, p.first_name
    """).fetchall()

    players = []
    for r in rows:
        players.append({
            "player_id":       r["player_id"],
            "sweater_number":  r["sweater_number"],
            "first_name":      r["first_name"],
            "last_name":       r["last_name"],
            "position_code":   r["position_code"] or "",
            "shoots_catches":  r["shoots_catches"] or "",
            "height":          _height_str(r["height_inches"]),
            "weight_pounds":   r["weight_pounds"],
            "birth_date":      r["birth_date"] or "",
            "birth_country":   r["birth_country"] or "",
            "team_abbrev":     r["team_abbrev"] or "",
            "team_name":       r["team_name"] or "",
            "team_place_name": r["team_place_name"] or "",
        })
    return players


@app.route("/api/players")
def api_players():
    conn = get_connection()
    players = _fetch_players(conn)
    conn.close()
    return jsonify(players)


@app.route("/api/players/stats")
def api_players_stats():
    seasons_param = request.args.get("seasons", "all")
    seasons = [s.strip() for s in seasons_param.split(",") if s.strip()]
    if not seasons:
        seasons = ["all"]
    conn = get_connection()

    if seasons == ["all"]:
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
        placeholders = ",".join("?" for _ in seasons)
        query = f"""
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
            WHERE s.season_id IN ({placeholders})
            GROUP BY p.player_id
            ORDER BY SUM(s.points) DESC
        """  # nosec B608 -- placeholders is only "?,?,..."; values are bound via `seasons` below, never interpolated
        rows = conn.execute(query, seasons).fetchall()

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


PERCENTILE_STRENGTH_STATES = ("5v5", "5v4", "4v5")


def _pct(numer, denom):
    return round(numer * 100.0 / denom, 1) if denom else None


def _fetch_player_advanced(conn, player_id, season_id):
    season_rows = conn.execute("""
        SELECT strength_state, cf, ca, ff, fa, hdcf, hdca, primary_points, team_abbrevs
        FROM player_season_advanced_stats
        WHERE player_id = ? AND season_id = ?
    """, (player_id, season_id)).fetchall()

    pctile_rows = conn.execute("""
        SELECT strength_state, cf_pct_pctile, ff_pct_pctile, hdcf_pct_pctile, primary_points_pctile
        FROM player_advanced_percentiles
        WHERE player_id = ? AND season_id = ?
    """, (player_id, season_id)).fetchall()
    pctiles_by_state = {r["strength_state"]: r for r in pctile_rows}

    strength_states = {}
    team_abbrevs = None
    for r in season_rows:
        state = r["strength_state"]
        pctile = pctiles_by_state.get(state)
        strength_states[state] = {
            "cf": r["cf"], "ca": r["ca"], "cf_pct": _pct(r["cf"], r["cf"] + r["ca"]),
            "ff": r["ff"], "fa": r["fa"], "ff_pct": _pct(r["ff"], r["ff"] + r["fa"]),
            "hdcf": r["hdcf"], "hdca": r["hdca"], "hdcf_pct": _pct(r["hdcf"], r["hdcf"] + r["hdca"]),
            "primary_points": r["primary_points"],
            "cf_pctile": pctile["cf_pct_pctile"] if pctile else None,
            "ff_pctile": pctile["ff_pct_pctile"] if pctile else None,
            "hdcf_pctile": pctile["hdcf_pct_pctile"] if pctile else None,
            "primary_points_pctile": pctile["primary_points_pctile"] if pctile else None,
        }
        if state == "5v5":
            team_abbrevs = r["team_abbrevs"]

    trend_rows = conn.execute("""
        SELECT season_id, cf, ca FROM player_season_advanced_stats
        WHERE player_id = ? AND strength_state = '5v5'
        ORDER BY season_id
    """, (player_id,)).fetchall()
    trend = [{"season_id": r["season_id"], "cf_pct": _pct(r["cf"], r["cf"] + r["ca"])}
             for r in trend_rows]

    pdo = None
    first_abbrev = (team_abbrevs or "").split(",")[0] if team_abbrevs else None
    if first_abbrev:
        team_row = conn.execute("""
            SELECT tsas.gf, tsas.ga, tsas.shots_for, tsas.shots_against
            FROM team_season_advanced_stats tsas
            JOIN teams t ON t.team_id = tsas.team_id
            WHERE t.abbrev = ? AND tsas.season_id = ? AND tsas.strength_state = '5v5'
        """, (first_abbrev, season_id)).fetchone()
        if team_row and team_row["shots_for"] and team_row["shots_against"]:
            shooting_pct = team_row["gf"] / team_row["shots_for"]
            save_pct = (team_row["shots_against"] - team_row["ga"]) / team_row["shots_against"]
            pdo = round((shooting_pct + save_pct) * 1000, 1)

    return {
        "player_id": player_id, "season_id": season_id,
        "strength_states": strength_states, "trend": trend, "pdo": pdo,
    }


def _fetch_team_advanced(conn, team_abbrev, season_id):
    rows = conn.execute("""
        SELECT tsas.strength_state, tsas.cf, tsas.ca, tsas.ff, tsas.fa,
               tsas.gf, tsas.ga, tsas.shots_for, tsas.shots_against
        FROM team_season_advanced_stats tsas
        JOIN teams t ON t.team_id = tsas.team_id
        WHERE t.abbrev = ? AND tsas.season_id = ?
    """, (team_abbrev, season_id)).fetchall()

    strength_states = {}
    for r in rows:
        pdo = None
        if r["shots_for"] and r["shots_against"]:
            shooting_pct = r["gf"] / r["shots_for"]
            save_pct = (r["shots_against"] - r["ga"]) / r["shots_against"]
            pdo = round((shooting_pct + save_pct) * 1000, 1)
        strength_states[r["strength_state"]] = {
            "cf": r["cf"], "ca": r["ca"], "cf_pct": _pct(r["cf"], r["cf"] + r["ca"]),
            "ff": r["ff"], "fa": r["fa"], "ff_pct": _pct(r["ff"], r["ff"] + r["fa"]),
            "gf": r["gf"], "ga": r["ga"], "pdo": pdo,
        }

    return {"team_abbrev": team_abbrev, "season_id": season_id, "strength_states": strength_states}


@app.route("/api/players/<int:player_id>/advanced")
def api_player_advanced(player_id):
    season_id = request.args.get("season")
    conn = get_connection()
    if not season_id:
        row = conn.execute(
            "SELECT MAX(season_id) AS s FROM player_season_advanced_stats WHERE player_id = ?",
            (player_id,),
        ).fetchone()
        season_id = row["s"] if row else None
    result = _fetch_player_advanced(conn, player_id, season_id) if season_id else {
        "player_id": player_id, "season_id": None, "strength_states": {}, "trend": [], "pdo": None,
    }
    conn.close()
    return jsonify(result)


@app.route("/api/teams/<team_abbrev>/advanced")
def api_team_advanced(team_abbrev):
    season_id = request.args.get("season")
    conn = get_connection()
    if not season_id:
        row = conn.execute("""
            SELECT MAX(tsas.season_id) AS s FROM team_season_advanced_stats tsas
            JOIN teams t ON t.team_id = tsas.team_id WHERE t.abbrev = ?
        """, (team_abbrev,)).fetchone()
        season_id = row["s"] if row else None
    result = _fetch_team_advanced(conn, team_abbrev, season_id) if season_id else {
        "team_abbrev": team_abbrev, "season_id": None, "strength_states": {},
    }
    conn.close()
    return jsonify(result)


def _debug_enabled():
    return os.environ.get("FLASK_DEBUG") == "1"


if __name__ == "__main__":
    app.run(debug=_debug_enabled(), port=5099)
