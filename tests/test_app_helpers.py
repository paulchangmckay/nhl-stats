from app import _toi_str, _height_str, _debug_enabled


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
