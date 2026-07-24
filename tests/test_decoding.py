from etl.advanced_stats.decoding import decode_strength_state, period_offset_seconds, elapsed_seconds

HOME = 1
AWAY = 2


def test_decode_5v5_both_goalies_in():
    assert decode_strength_state("1551", event_owner_team_id=HOME, home_team_id=HOME) == "5v5"


def test_decode_home_power_play():
    # away down to 4, home has 5 -> from home's (shooting) perspective, 5v4
    assert decode_strength_state("1451", event_owner_team_id=HOME, home_team_id=HOME) == "5v4"


def test_decode_away_shorthanded_from_away_perspective():
    # same code, but away is shooting -> from away's perspective, 4v5
    assert decode_strength_state("1451", event_owner_team_id=AWAY, home_team_id=HOME) == "4v5"


def test_decode_5_on_3():
    assert decode_strength_state("1351", event_owner_team_id=HOME, home_team_id=HOME) == "5v3"


def test_decode_both_goalies_pulled():
    assert decode_strength_state("0440", event_owner_team_id=HOME, home_team_id=HOME) == "4v4"


def test_decode_malformed_code_returns_other():
    assert decode_strength_state("bogus", event_owner_team_id=HOME, home_team_id=HOME) == "other"
    assert decode_strength_state(None, event_owner_team_id=HOME, home_team_id=HOME) == "other"
    assert decode_strength_state("12", event_owner_team_id=HOME, home_team_id=HOME) == "other"


def test_period_offset_regulation_periods_fixed_1200s():
    assert period_offset_seconds(1, "REG", game_type=2) == 0
    assert period_offset_seconds(2, "REG", game_type=2) == 1200
    assert period_offset_seconds(3, "REG", game_type=2) == 2400


def test_period_offset_regular_season_ot_is_300s():
    assert period_offset_seconds(4, "OT", game_type=2) == 3600
    assert period_offset_seconds(5, "OT", game_type=2) == 3900


def test_period_offset_playoff_ot_is_1200s():
    assert period_offset_seconds(4, "OT", game_type=3) == 3600
    assert period_offset_seconds(5, "OT", game_type=3) == 4800


def test_elapsed_seconds_combines_offset_and_clock():
    assert elapsed_seconds("00:08", period=1, period_type="REG", game_type=2) == 8
    assert elapsed_seconds("03:24", period=4, period_type="OT", game_type=2) == 3600 + 204
