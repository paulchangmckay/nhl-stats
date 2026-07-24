from etl.advanced_stats.sweep import compute_game_advanced_stats

HOME = 1
AWAY = 2


def _shift(player_id, team_id, period, start, end, position_code="C", period_type="REG"):
    return {"player_id": player_id, "team_id": team_id, "period": period,
            "start_time": start, "end_time": end, "position_code": position_code,
            "period_type": period_type}


def _event(event_type, period, time_in_period, situation_code, event_owner_team_id,
           x_coord=0, y_coord=0, period_type="REG", shooting_player_id=None,
           assist1_player_id=None):
    return {"event_type": event_type, "period": period, "time_in_period": time_in_period,
            "situation_code": situation_code, "event_owner_team_id": event_owner_team_id,
            "x_coord": x_coord, "y_coord": y_coord, "period_type": period_type,
            "shooting_player_id": shooting_player_id, "assist1_player_id": assist1_player_id,
            "home_team_defending_side": "right"}


def test_shot_credits_on_ice_skaters_both_sides():
    shifts = [
        _shift(1, HOME, 1, "00:00", "20:00"),
        _shift(2, AWAY, 1, "00:00", "20:00"),
    ]
    events = [_event("shot-on-goal", 1, "00:10", "1551", HOME)]

    player_rows, team_rows = compute_game_advanced_stats(shifts, events, home_team_id=HOME, game_type=2)

    home_row = next(r for r in player_rows if r["player_id"] == 1)
    away_row = next(r for r in player_rows if r["player_id"] == 2)
    assert home_row["cf"] == 1 and home_row["ca"] == 0
    assert away_row["ca"] == 1 and away_row["cf"] == 0


def test_blocked_shot_counts_corsi_not_fenwick():
    shifts = [_shift(1, HOME, 1, "00:00", "20:00"), _shift(2, AWAY, 1, "00:00", "20:00")]
    events = [_event("blocked-shot", 1, "00:10", "1551", HOME)]

    player_rows, _ = compute_game_advanced_stats(shifts, events, home_team_id=HOME, game_type=2)
    home_row = next(r for r in player_rows if r["player_id"] == 1)
    assert home_row["cf"] == 1
    assert home_row["ff"] == 0


def test_goalie_excluded_from_skater_credit():
    shifts = [
        _shift(1, HOME, 1, "00:00", "20:00", position_code="C"),
        _shift(99, HOME, 1, "00:00", "20:00", position_code="G"),
        _shift(2, AWAY, 1, "00:00", "20:00"),
    ]
    events = [_event("shot-on-goal", 1, "00:10", "1551", HOME)]

    player_rows, _ = compute_game_advanced_stats(shifts, events, home_team_id=HOME, game_type=2)
    goalie_rows = [r for r in player_rows if r["player_id"] == 99]
    assert goalie_rows == []


def test_shift_with_no_end_time_closes_at_period_boundary():
    shifts = [
        _shift(1, HOME, 1, "18:00", None),
        _shift(2, AWAY, 1, "00:00", "20:00"),
    ]
    events = [_event("shot-on-goal", 1, "19:00", "1551", HOME)]

    player_rows, _ = compute_game_advanced_stats(shifts, events, home_team_id=HOME, game_type=2)
    home_row = next(r for r in player_rows if r["player_id"] == 1)
    assert home_row["cf"] == 1


def test_shootout_period_excluded_entirely():
    shifts = [_shift(1, HOME, 5, "00:00", "00:30", period_type="SO")]
    events = [_event("goal", 5, "00:10", "1010", HOME, period_type="SO")]

    player_rows, team_rows = compute_game_advanced_stats(shifts, events, home_team_id=HOME, game_type=2)
    assert player_rows == []
    assert team_rows == []


def test_strength_state_generic_not_coerced_to_fixed_bucket():
    shifts = [
        _shift(1, HOME, 1, "00:00", "20:00"),
        _shift(2, HOME, 1, "00:00", "20:00"),
        _shift(3, HOME, 1, "00:00", "20:00"),
        _shift(4, HOME, 1, "00:00", "20:00"),
        _shift(5, HOME, 1, "00:00", "20:00"),
        _shift(6, AWAY, 1, "00:00", "20:00"),
        _shift(7, AWAY, 1, "00:00", "20:00"),
        _shift(8, AWAY, 1, "00:00", "20:00"),
    ]
    # 1351 = away down to 3 vs home's 5 -> a 5-on-3
    events = [_event("shot-on-goal", 1, "00:10", "1351", HOME)]

    player_rows, _ = compute_game_advanced_stats(shifts, events, home_team_id=HOME, game_type=2)
    # player 1 has two rows: a 5v5 bucket for the TOI before this event told
    # the sweep the real strength state, and the 5v3 bucket the shot itself
    # (and the remaining TOI) belongs to -- both are correct, not a bug.
    shot_row = next(r for r in player_rows if r["player_id"] == 1 and r["cf"] > 0)
    assert shot_row["strength_state"] == "5v3"


def test_primary_points_needs_no_on_ice_data():
    events = [_event("goal", 1, "05:00", "1551", HOME, shooting_player_id=1, assist1_player_id=2)]
    player_rows, _ = compute_game_advanced_stats([], events, home_team_id=HOME, game_type=2)

    scorer_row = next(r for r in player_rows if r["player_id"] == 1)
    assister_row = next(r for r in player_rows if r["player_id"] == 2)
    assert scorer_row["primary_points"] == 1
    assert assister_row["primary_points"] == 1


def test_goal_increments_gf_ga_for_on_ice_teams():
    shifts = [_shift(1, HOME, 1, "00:00", "20:00"), _shift(2, AWAY, 1, "00:00", "20:00")]
    events = [_event("goal", 1, "00:10", "1551", HOME, shooting_player_id=1)]

    player_rows, team_rows = compute_game_advanced_stats(shifts, events, home_team_id=HOME, game_type=2)
    home_player_row = next(r for r in player_rows if r["player_id"] == 1)
    away_player_row = next(r for r in player_rows if r["player_id"] == 2)
    assert home_player_row["gf"] == 1
    assert away_player_row["ga"] == 1

    home_team_row = next(r for r in team_rows if r["team_id"] == HOME)
    away_team_row = next(r for r in team_rows if r["team_id"] == AWAY)
    assert home_team_row["gf"] == 1
    assert away_team_row["ga"] == 1


def test_toi_seconds_accumulates_for_on_ice_skaters():
    shifts = [
        _shift(1, HOME, 1, "00:00", "00:30"),
        _shift(2, AWAY, 1, "00:00", "00:30"),
    ]
    # no shot events -- just confirm TOI accrues from the shift interval itself
    events = [_event("faceoff", 1, "00:00", "1551", HOME)]

    player_rows, _ = compute_game_advanced_stats(shifts, events, home_team_id=HOME, game_type=2)
    home_row = next(r for r in player_rows if r["player_id"] == 1)
    assert home_row["toi_seconds"] == 30
