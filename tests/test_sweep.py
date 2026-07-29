from etl.advanced_stats.sweep import compute_game_advanced_stats

HOME = 1
AWAY = 2


def _shift(player_id, team_id, period, start, end, position_code="C"):
    return {"player_id": player_id, "team_id": team_id, "period": period,
            "start_time": start, "end_time": end, "position_code": position_code}


def _event(event_type, period, time_in_period, situation_code, event_owner_team_id,
           x_coord=0, y_coord=0, shooting_player_id=None, assist1_player_id=None,
           assist2_player_id=None, shot_type=None):
    return {"event_type": event_type, "period": period, "time_in_period": time_in_period,
            "situation_code": situation_code, "event_owner_team_id": event_owner_team_id,
            "x_coord": x_coord, "y_coord": y_coord,
            "shooting_player_id": shooting_player_id, "assist1_player_id": assist1_player_id,
            "assist2_player_id": assist2_player_id, "shot_type": shot_type,
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


def test_shootout_period_excluded_entirely_for_regular_season_game():
    # No period_type field exists anywhere in the real schema (game_events/
    # player_shifts only ever have a plain period number) -- shootout status
    # must be derived from period + game_type, confirmed via live NHL API
    # fetch that period 5 is always the shootout for a regular-season game
    # (game_type=2), never a second OT period.
    shifts = [_shift(1, HOME, 5, "00:00", "00:30")]
    events = [_event("goal", 5, "00:10", "1010", HOME)]

    player_rows, team_rows = compute_game_advanced_stats(shifts, events, home_team_id=HOME, game_type=2)
    assert player_rows == []
    assert team_rows == []


def test_period_5_not_excluded_for_playoff_game_since_playoffs_have_no_shootout():
    # Confirmed via live NHL API fetch: playoff games (game_type=3) never go
    # to a shootout -- period 5+ is always another full OT period, and must
    # be processed normally, not excluded as if it were a shootout.
    shifts = [
        _shift(1, HOME, 5, "00:00", "20:00"),
        _shift(2, AWAY, 5, "00:00", "20:00"),
    ]
    events = [_event("shot-on-goal", 5, "00:10", "1551", HOME)]

    player_rows, _ = compute_game_advanced_stats(shifts, events, home_team_id=HOME, game_type=3)
    home_row = next((r for r in player_rows if r["player_id"] == 1), None)
    assert home_row is not None
    assert home_row["cf"] == 1


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


def test_individual_shot_credit_only_on_shooter_not_teammates():
    shifts = [_shift(1, HOME, 1, "00:00", "20:00"), _shift(2, HOME, 1, "00:00", "20:00"),
              _shift(3, AWAY, 1, "00:00", "20:00")]
    events = [_event("shot-on-goal", 1, "00:10", "1551", HOME, shooting_player_id=1)]

    player_rows, _ = compute_game_advanced_stats(shifts, events, home_team_id=HOME, game_type=2)
    shooter_row = next(r for r in player_rows if r["player_id"] == 1)
    teammate_row = next(r for r in player_rows if r["player_id"] == 2)
    assert shooter_row["icf"] == 1
    assert teammate_row["icf"] == 0
    assert shooter_row["cf"] == 1 and teammate_row["cf"] == 1  # on-ice credit unaffected


def test_individual_high_danger_and_deflection_credit():
    shifts = [_shift(1, HOME, 1, "00:00", "20:00"), _shift(2, AWAY, 1, "00:00", "20:00")]
    events = [_event("shot-on-goal", 1, "00:10", "1551", HOME, x_coord=85, y_coord=0,
                      shooting_player_id=1, shot_type="deflected")]

    player_rows, _ = compute_game_advanced_stats(shifts, events, home_team_id=HOME, game_type=2)
    shooter_row = next(r for r in player_rows if r["player_id"] == 1)
    assert shooter_row["ihdcf"] == 1
    assert shooter_row["deflections"] == 1


def test_rebound_credited_to_original_shooter_within_3_seconds():
    shifts = [_shift(1, HOME, 1, "00:00", "20:00"), _shift(2, HOME, 1, "00:00", "20:00")]
    events = [
        _event("shot-on-goal", 1, "00:10", "1551", HOME, shooting_player_id=1),
        _event("shot-on-goal", 1, "00:12", "1551", HOME, shooting_player_id=2),
    ]
    player_rows, _ = compute_game_advanced_stats(shifts, events, home_team_id=HOME, game_type=2)
    original = next(r for r in player_rows if r["player_id"] == 1)
    rebounder = next(r for r in player_rows if r["player_id"] == 2)
    assert original["rebounds_created"] == 1
    assert rebounder["rebounds_created"] == 0


def test_rebound_boundary_exactly_3_seconds_counts():
    shifts = [_shift(1, HOME, 1, "00:00", "20:00"), _shift(2, HOME, 1, "00:00", "20:00")]
    events = [
        _event("shot-on-goal", 1, "00:10", "1551", HOME, shooting_player_id=1),
        _event("shot-on-goal", 1, "00:13", "1551", HOME, shooting_player_id=2),
    ]
    player_rows, _ = compute_game_advanced_stats(shifts, events, home_team_id=HOME, game_type=2)
    original = next(r for r in player_rows if r["player_id"] == 1)
    assert original["rebounds_created"] == 1


def test_rebound_beyond_window_does_not_count():
    shifts = [_shift(1, HOME, 1, "00:00", "20:00"), _shift(2, HOME, 1, "00:00", "20:00")]
    events = [
        _event("shot-on-goal", 1, "00:10", "1551", HOME, shooting_player_id=1),
        _event("shot-on-goal", 1, "00:14", "1551", HOME, shooting_player_id=2),
    ]
    player_rows, _ = compute_game_advanced_stats(shifts, events, home_team_id=HOME, game_type=2)
    original = next(r for r in player_rows if r["player_id"] == 1)
    assert original["rebounds_created"] == 0


def test_rebound_different_teams_does_not_count():
    shifts = [_shift(1, HOME, 1, "00:00", "20:00"), _shift(2, AWAY, 1, "00:00", "20:00")]
    events = [
        _event("shot-on-goal", 1, "00:10", "1551", HOME, shooting_player_id=1),
        _event("shot-on-goal", 1, "00:11", "1551", AWAY, shooting_player_id=2),
    ]
    player_rows, _ = compute_game_advanced_stats(shifts, events, home_team_id=HOME, game_type=2)
    home_shooter = next(r for r in player_rows if r["player_id"] == 1)
    assert home_shooter["rebounds_created"] == 0


def test_rebound_same_player_consecutive_shots_counts():
    shifts = [_shift(1, HOME, 1, "00:00", "20:00")]
    events = [
        _event("shot-on-goal", 1, "00:10", "1551", HOME, shooting_player_id=1),
        _event("shot-on-goal", 1, "00:12", "1551", HOME, shooting_player_id=1),
    ]
    player_rows, _ = compute_game_advanced_stats(shifts, events, home_team_id=HOME, game_type=2)
    shooter_row = next(r for r in player_rows if r["player_id"] == 1)
    assert shooter_row["rebounds_created"] == 1


def test_rebound_scramble_credits_each_pair_independently():
    shifts = [_shift(1, HOME, 1, "00:00", "20:00"), _shift(2, HOME, 1, "00:00", "20:00"),
              _shift(3, HOME, 1, "00:00", "20:00")]
    events = [
        _event("shot-on-goal", 1, "00:10", "1551", HOME, shooting_player_id=1),
        _event("shot-on-goal", 1, "00:12", "1551", HOME, shooting_player_id=2),
        _event("shot-on-goal", 1, "00:14", "1551", HOME, shooting_player_id=3),
    ]
    player_rows, _ = compute_game_advanced_stats(shifts, events, home_team_id=HOME, game_type=2)
    p1 = next(r for r in player_rows if r["player_id"] == 1)
    p2 = next(r for r in player_rows if r["player_id"] == 2)
    p3 = next(r for r in player_rows if r["player_id"] == 3)
    assert p1["rebounds_created"] == 1
    assert p2["rebounds_created"] == 1
    assert p3["rebounds_created"] == 0


def test_points_credits_scorer_and_both_assists_primary_points_excludes_secondary():
    events = [_event("goal", 1, "05:00", "1551", HOME, shooting_player_id=1,
                      assist1_player_id=2, assist2_player_id=3)]
    player_rows, _ = compute_game_advanced_stats([], events, home_team_id=HOME, game_type=2)

    scorer = next(r for r in player_rows if r["player_id"] == 1)
    primary_assister = next(r for r in player_rows if r["player_id"] == 2)
    secondary_assister = next(r for r in player_rows if r["player_id"] == 3)

    assert scorer["points"] == 1 and scorer["primary_points"] == 1
    assert primary_assister["points"] == 1 and primary_assister["primary_points"] == 1
    assert secondary_assister["points"] == 1 and secondary_assister["primary_points"] == 0
