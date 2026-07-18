from etl.load_historical_schedule import _map_game_state, _extract_game


def test_map_game_state_known_value_returns_off():
    assert _map_game_state(7) == "OFF"


def test_map_game_state_unknown_value_falls_back_to_raw_string():
    assert _map_game_state(99) == "99"


def test_extract_game_maps_all_fields():
    raw = {
        "id": 2024020001, "season": 20242025, "gameType": 2,
        "gameDate": "2024-10-04", "homeTeamId": 7, "visitingTeamId": 1,
        "homeScore": 1, "visitingScore": 4, "gameStateId": 7,
    }
    game = _extract_game(raw)

    assert game.game_id == 2024020001
    assert game.season_id == "20242025"
    assert game.game_type == 2
    assert game.game_date == "2024-10-04"
    assert game.home_team_id == 7
    assert game.away_team_id == 1
    assert game.home_score == 1
    assert game.away_score == 4
    assert game.game_state == "OFF"
    assert game.venue is None
    assert game.last_period_type is None
