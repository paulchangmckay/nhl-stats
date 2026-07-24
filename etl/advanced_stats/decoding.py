REGULATION_PERIOD_SECONDS = 1200
REGULAR_SEASON_OT_SECONDS = 300
PLAYOFF_OT_SECONDS = 1200


def decode_strength_state(situation_code, event_owner_team_id, home_team_id):
    """situation_code is [awayGoalieInNet][awaySkaters][homeSkaters][homeGoalieInNet],
    confirmed via live NHL API samples (games 2020020003, 2020020007). Returns
    a generic '{shooting}v{opposing}' string oriented to the shooting team's
    perspective, or 'other' for anything that doesn't parse as 4 digits."""
    if not situation_code or len(situation_code) != 4 or not situation_code.isdigit():
        return "other"

    away_skaters = int(situation_code[1])
    home_skaters = int(situation_code[2])

    if event_owner_team_id == home_team_id:
        return f"{home_skaters}v{away_skaters}"
    return f"{away_skaters}v{home_skaters}"


def period_offset_seconds(period, period_type, game_type):
    """Cumulative elapsed-seconds offset at the start of `period`. Regulation
    periods (1-3) are always 1200s. OT length depends on game_type: 300s for
    regular season (game_type=2, single 3-on-3 period), 1200s for playoffs
    (game_type=3, full sudden-death periods) -- confirmed via live fetch that
    a regular-season OT period ends by ~300s (game 2020020003)."""
    if period <= 3:
        return (period - 1) * REGULATION_PERIOD_SECONDS

    ot_period_length = REGULAR_SEASON_OT_SECONDS if game_type == 2 else PLAYOFF_OT_SECONDS
    ot_periods_elapsed = period - 4
    return 3 * REGULATION_PERIOD_SECONDS + ot_periods_elapsed * ot_period_length


def elapsed_seconds(clock, period, period_type, game_type):
    minutes, seconds = clock.split(":")
    within_period = int(minutes) * 60 + int(seconds)
    return period_offset_seconds(period, period_type, game_type) + within_period
