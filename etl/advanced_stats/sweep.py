from etl.advanced_stats.decoding import decode_strength_state, elapsed_seconds, period_offset_seconds

SHOT_ATTEMPT_TYPES = {"shot-on-goal", "missed-shot", "blocked-shot", "goal"}
FENWICK_TYPES = {"shot-on-goal", "missed-shot", "goal"}  # excludes blocked-shot
GOAL_SHOT_TYPES = {"shot-on-goal", "goal"}  # count toward shots_for/against
SKATER_POSITIONS = {"C", "L", "R", "D"}

# Rough NHL "inner slot" high-danger zone: within 20ft of the net (net sits at
# x=+/-89 on a standard 200x85ft rink), between the width of the faceoff dots.
# Exact boundary is a defensible starting default, not a literature constant --
# revisit if HDSC numbers look off during the Task 10 spot-check.
HIGH_DANGER_X_MIN = 69
HIGH_DANGER_Y_ABS_MAX = 22


def _is_high_danger(x_coord, y_coord, home_team_defending_side, is_home_shooter):
    if x_coord is None or y_coord is None or home_team_defending_side is None:
        return False
    # Normalize so the shooting team's attacking net is always at positive x.
    attacking_positive_x = (
        home_team_defending_side == "left" if is_home_shooter
        else home_team_defending_side == "right"
    )
    x = x_coord if attacking_positive_x else -x_coord
    return x >= HIGH_DANGER_X_MIN and abs(y_coord) <= HIGH_DANGER_Y_ABS_MAX


def _is_shootout(period, game_type):
    """No period_type field exists anywhere in this codebase's schema --
    game_events/player_shifts only ever carry a plain period number.
    Shootout status is fully derivable from period + game_type instead:
    confirmed via live NHL API fetch (games 2020020007) that a regular-
    season game (game_type=2) always has its shootout at exactly period 5
    (3 regulation + 1 single 3-on-3 OT period, never a second OT), while
    playoff games (game_type=3) never have a shootout at all -- period 5+
    there is always another full sudden-death OT period and must be
    processed normally."""
    return game_type == 2 and period >= 5


def compute_game_advanced_stats(shifts, events, home_team_id, game_type):
    shifts = [s for s in shifts if not _is_shootout(s["period"], game_type)]
    events = [e for e in events if not _is_shootout(e["period"], game_type)]

    shift_intervals = []
    for s in shifts:
        if s.get("position_code") not in SKATER_POSITIONS:
            continue
        start = elapsed_seconds(s["start_time"], s["period"], game_type)
        if s.get("end_time"):
            end = elapsed_seconds(s["end_time"], s["period"], game_type)
        else:
            end = period_offset_seconds(s["period"] + 1, game_type)
        shift_intervals.append({"player_id": s["player_id"], "team_id": s["team_id"],
                                 "start": start, "end": end})

    event_list = []
    for e in events:
        t = elapsed_seconds(e["time_in_period"], e["period"], game_type)
        event_list.append({**e, "t": t})
    event_list.sort(key=lambda e: e["t"])

    game_has_rink_side_data = any(
        e["event_type"] in SHOT_ATTEMPT_TYPES and e.get("home_team_defending_side") is not None
        for e in event_list
    )

    all_team_ids = {iv["team_id"] for iv in shift_intervals if iv["team_id"] is not None}
    all_team_ids |= {e.get("event_owner_team_id") for e in event_list
                      if e.get("event_owner_team_id") is not None}
    away_team_id = next((tid for tid in all_team_ids if tid != home_team_id), None)

    player_stats = {}
    team_stats = {}

    def player_row(player_id, team_id, strength_state):
        key = (player_id, strength_state)
        if key not in player_stats:
            player_stats[key] = {
                "player_id": player_id, "team_id": team_id, "strength_state": strength_state,
                "cf": 0, "ca": 0, "ff": 0, "fa": 0, "hdcf": 0, "hdca": 0,
                "gf": 0, "ga": 0, "primary_points": 0, "toi_seconds": 0,
                "icf": 0, "ihdcf": 0, "rebounds_created": 0, "deflections": 0, "points": 0,
            }
        return player_stats[key]

    def team_row(team_id, strength_state):
        key = (team_id, strength_state)
        if key not in team_stats:
            team_stats[key] = {
                "team_id": team_id, "strength_state": strength_state,
                "cf": 0, "ca": 0, "ff": 0, "fa": 0, "gf": 0, "ga": 0,
                "shots_for": 0, "shots_against": 0,
            }
        return team_stats[key]

    def on_ice(team_id, t):
        return [iv["player_id"] for iv in shift_intervals
                if iv["team_id"] == team_id and iv["start"] <= t < iv["end"]]

    # Primary points -- independent of on-ice reconstruction entirely.
    for e in event_list:
        if e["event_type"] != "goal":
            continue
        owner = e.get("event_owner_team_id")
        if owner is None:
            continue
        strength_state = decode_strength_state(e.get("situation_code"), owner, home_team_id)
        scorer = e.get("shooting_player_id")
        if scorer is not None:
            player_row(scorer, owner, strength_state)["primary_points"] += 1
            player_row(scorer, owner, strength_state)["points"] += 1
        assist1 = e.get("assist1_player_id")
        if assist1 is not None:
            player_row(assist1, owner, strength_state)["primary_points"] += 1
            player_row(assist1, owner, strength_state)["points"] += 1
        assist2 = e.get("assist2_player_id")
        if assist2 is not None:
            player_row(assist2, owner, strength_state)["points"] += 1

    # TOI accumulation: walk every distinct shift-boundary/event timestamp,
    # crediting on-ice skaters for the interval up to the next timestamp at
    # whichever strength state was last seen (defaulting to 5v5 pre-first-event).
    breakpoints = sorted({iv["start"] for iv in shift_intervals}
                         | {iv["end"] for iv in shift_intervals}
                         | {e["t"] for e in event_list})

    current_strength = {home_team_id: "5v5"}
    if away_team_id is not None:
        current_strength[away_team_id] = "5v5"

    event_idx = 0
    for i in range(len(breakpoints) - 1):
        t0, t1 = breakpoints[i], breakpoints[i + 1]
        while event_idx < len(event_list) and event_list[event_idx]["t"] <= t0:
            e = event_list[event_idx]
            owner = e.get("event_owner_team_id")
            sc = e.get("situation_code")
            if owner is not None:
                current_strength[home_team_id] = decode_strength_state(sc, home_team_id, home_team_id)
                if away_team_id is not None:
                    current_strength[away_team_id] = decode_strength_state(sc, away_team_id, home_team_id)
            event_idx += 1

        duration = t1 - t0
        if duration <= 0:
            continue
        for team_id in (home_team_id, away_team_id):
            if team_id is None:
                continue
            strength_state = current_strength.get(team_id, "5v5")
            for player_id in on_ice(team_id, t0):
                player_row(player_id, team_id, strength_state)["toi_seconds"] += duration

    # Shot-attempt credit (Corsi/Fenwick/HDSC/goals-for-against), player + team grain.
    last_shot_attempt = {}
    for e in event_list:
        if e["event_type"] not in SHOT_ATTEMPT_TYPES:
            continue
        owner = e.get("event_owner_team_id")
        if owner is None:
            continue
        opposing = away_team_id if owner == home_team_id else home_team_id
        t = e["t"]
        strength_for = decode_strength_state(e.get("situation_code"), owner, home_team_id)
        strength_against = (decode_strength_state(e.get("situation_code"), opposing, home_team_id)
                             if opposing is not None else strength_for)

        is_fenwick = e["event_type"] in FENWICK_TYPES
        is_goal = e["event_type"] == "goal"
        is_shot_stat = e["event_type"] in GOAL_SHOT_TYPES
        high_danger = _is_high_danger(e.get("x_coord"), e.get("y_coord"),
                                       e.get("home_team_defending_side"),
                                       is_home_shooter=(owner == home_team_id))
        is_deflection = e.get("shot_type") in ("deflected", "tip-in")

        for player_id in on_ice(owner, t):
            row = player_row(player_id, owner, strength_for)
            row["cf"] += 1
            if is_fenwick:
                row["ff"] += 1
            if high_danger:
                row["hdcf"] += 1
            if is_goal:
                row["gf"] += 1

        if opposing is not None:
            for player_id in on_ice(opposing, t):
                row = player_row(player_id, opposing, strength_against)
                row["ca"] += 1
                if is_fenwick:
                    row["fa"] += 1
                if high_danger:
                    row["hdca"] += 1
                if is_goal:
                    row["ga"] += 1

        shooter = e.get("shooting_player_id")
        if shooter is not None:
            shooter_row = player_row(shooter, owner, strength_for)
            shooter_row["icf"] += 1
            if high_danger:
                shooter_row["ihdcf"] += 1
            if is_deflection:
                shooter_row["deflections"] += 1

            prior = last_shot_attempt.get(owner)
            if prior is not None and (t - prior[0]) <= 3:
                player_row(prior[1], owner, prior[2])["rebounds_created"] += 1
            last_shot_attempt[owner] = (t, shooter, strength_for)

        t_for = team_row(owner, strength_for)
        t_for["cf"] += 1
        if is_fenwick:
            t_for["ff"] += 1
        if is_shot_stat:
            t_for["shots_for"] += 1
        if is_goal:
            t_for["gf"] += 1

        if opposing is not None:
            t_against = team_row(opposing, strength_against)
            t_against["ca"] += 1
            if is_fenwick:
                t_against["fa"] += 1
            if is_shot_stat:
                t_against["shots_against"] += 1
            if is_goal:
                t_against["ga"] += 1

    if not game_has_rink_side_data:
        for row in player_stats.values():
            row["hdcf"] = None
            row["hdca"] = None
            row["ihdcf"] = None

    return list(player_stats.values()), list(team_stats.values())
