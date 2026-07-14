from app import _toi_str, _height_str, _debug_enabled, _fetch_players
from src import database


def test_toi_str_converts_decimal_seconds_to_mmss():
    assert _toi_str("125.5") == "2:05"


def test_toi_str_pads_single_digit_seconds():
    assert _toi_str("61") == "1:01"


def test_toi_str_returns_empty_string_for_none():
    assert _toi_str(None) == ""


def test_toi_str_returns_raw_value_for_non_numeric_string():
    assert _toi_str("MM:SS") == "MM:SS"


def test_height_str_formats_feet_and_inches():
    assert _height_str(73) == "6'1\""


def test_height_str_returns_empty_string_for_none():
    assert _height_str(None) == ""


def test_debug_enabled_true_when_env_var_is_one(monkeypatch):
    monkeypatch.setenv("FLASK_DEBUG", "1")
    assert _debug_enabled() is True


def test_debug_enabled_false_when_env_var_unset(monkeypatch):
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    assert _debug_enabled() is False


def test_debug_enabled_false_for_any_other_value(monkeypatch):
    monkeypatch.setenv("FLASK_DEBUG", "true")
    assert _debug_enabled() is False


def test_fetch_players_includes_team_place_name(conn):
    """Regression for issue #10: team-name search needs the full place name
    (e.g. "Colorado"), not just the short common_name ("Avalanche") or
    abbreviation ("COL"), so it must be exposed by the players query."""
    database.upsert_team(conn, {
        "team_id": 21, "abbrev": "COL", "common_name": "Avalanche",
        "place_name": "Colorado", "conference": "Western", "division": "Central",
    })
    database.upsert_player_stub(conn, {
        "player_id": 1, "first_name": "Nathan", "last_name": "MacKinnon",
        "position_code": "C", "shoots_catches": "L",
    })
    conn.execute(
        "UPDATE players SET current_team_id = ? WHERE player_id = ?", (21, 1)
    )
    conn.commit()

    players = _fetch_players(conn)

    assert len(players) == 1
    assert players[0]["team_place_name"] == "Colorado"
