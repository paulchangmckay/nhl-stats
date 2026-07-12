import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import api_client, database


def _safe_get(d, *keys, default=None):
    """Safely navigate nested dicts."""
    for key in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(key)
    return d if d is not None else default


def _extract_skater_season(totals):
    return {
        "gp":           totals.get("gamesPlayed"),
        "goals":        totals.get("goals"),
        "assists":      totals.get("assists"),
        "points":       totals.get("points"),
        "plus_minus":   totals.get("plusMinus"),
        "pim":          totals.get("pim"),
        "pp_goals":     totals.get("powerPlayGoals"),
        "sh_goals":     totals.get("shorthandedGoals"),
        "shots":        totals.get("shots"),
        "shooting_pct": totals.get("shootingPctg"),
        "avg_toi":      totals.get("avgToi"),
    }


def _extract_goalie_season(totals):
    return {
        "gp":       totals.get("gamesPlayed"),
        "wins":     totals.get("wins"),
        "losses":   totals.get("losses"),
        "ot_losses": totals.get("otLosses"),
        "save_pct": totals.get("savePctg"),
        "gaa":      totals.get("goalsAgainstAvg"),
        "shutouts": totals.get("shutouts"),
    }


def _build_career_row(player_id, career_totals, position_code):
    is_goalie = position_code == "G"
    rs = career_totals.get("regularSeason") or {}
    po = career_totals.get("playoffs") or {}

    row = {"player_id": player_id}

    if is_goalie:
        g = _extract_goalie_season(rs)
        row.update({f"rs_{k}": v for k, v in g.items()})
        g = _extract_goalie_season(po)
        row.update({f"po_{k}": v for k, v in g.items()})
    else:
        s = _extract_skater_season(rs)
        row.update({f"rs_{k}": v for k, v in s.items()})
        s = _extract_skater_season(po)
        row.update({f"po_{k}": v for k, v in s.items()})

    return row


def run(conn):
    players = conn.execute("""
        SELECT player_id, position_code FROM players
        WHERE enriched_at IS NULL
           OR height_inches IS NULL
           OR position_code IS NULL
           OR (is_active = 1 AND enriched_at < datetime('now', '-7 days'))
        ORDER BY player_id
    """).fetchall()

    total = len(players)
    if total == 0:
        print("  No players need enrichment.")
        return

    estimate_min = round(total * 0.5 / 60, 1)
    print(f"Enriching {total} players via landing API (~{estimate_min} min at 0.5s/player)...")

    done = 0
    errors = 0

    for row in players:
        player_id = row["player_id"]
        position_code = row["position_code"]

        try:
            data = api_client.get_player_landing(player_id)
        except Exception as e:
            print(f"  Warning: could not fetch landing for {player_id}: {e}")
            errors += 1
            time.sleep(1)
            continue

        # ── Bio / draft enrichment ─────────────────────────────────────────
        draft = data.get("draftDetails") or {}
        birth_city_raw = data.get("birthCity")
        birth_city = birth_city_raw.get("default") if isinstance(birth_city_raw, dict) else birth_city_raw
        birth_state_raw = data.get("birthStateProvince")
        birth_state = birth_state_raw.get("default") if isinstance(birth_state_raw, dict) else birth_state_raw

        api_position = data.get("position") or None

        database.upsert_player_enrichment(conn, {
            "player_id":           player_id,
            "draft_year":          draft.get("year"),
            "draft_round":         draft.get("round"),
            "draft_pick":          draft.get("pickInRound"),
            "draft_overall":       draft.get("overallPick"),
            "draft_team_abbrev":   draft.get("teamAbbrev"),
            "is_active":           1 if data.get("isActive") else 0,
            "position_code":       api_position,
            "birth_city":          birth_city,
            "birth_state_province": birth_state,
            "headshot_url":        data.get("headshot"),
            "height_inches":       data.get("heightInInches"),
            "weight_pounds":       data.get("weightInPounds"),
            "birth_date":          data.get("birthDate"),
            "birth_country":       data.get("birthCountry"),
        })

        # ── Career totals ──────────────────────────────────────────────────
        career_totals = data.get("careerTotals") or {}
        if career_totals:
            effective_position = api_position or position_code or ""
            career_row = _build_career_row(player_id, career_totals, effective_position)
            database.upsert_career_stats(conn, career_row)

        done += 1
        if done % 50 == 0:
            conn.commit()
            print(f"  {done}/{total} enriched...")
        time.sleep(0.5)

    conn.commit()
    print(f"  Done. {done} enriched, {errors} errors.")


if __name__ == "__main__":
    conn = database.get_connection()
    run(conn)
    conn.close()
