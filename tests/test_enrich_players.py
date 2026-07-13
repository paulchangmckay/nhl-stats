from etl.enrich_players import _safe_get, _extract_skater_season, _build_career_row


def test_safe_get_navigates_nested_dict():
    d = {"a": {"b": {"c": 42}}}
    assert _safe_get(d, "a", "b", "c") == 42


def test_safe_get_returns_default_when_key_missing():
    assert _safe_get({"a": {}}, "a", "b", "c", default="missing") == "missing"


def test_safe_get_returns_default_when_intermediate_value_is_not_a_dict():
    assert _safe_get({"a": "not-a-dict"}, "a", "b", default="missing") == "missing"


def test_safe_get_returns_default_when_value_is_none():
    assert _safe_get({"a": None}, "a", default="fallback") == "fallback"


def test_extract_skater_season_maps_api_field_names():
    totals = {"gamesPlayed": 82, "goals": 30, "assists": 40, "points": 70}
    result = _extract_skater_season(totals)
    assert result["gp"] == 82
    assert result["goals"] == 30
    assert result["assists"] == 40
    assert result["points"] == 70


def test_build_career_row_uses_goalie_extractor_for_position_g():
    career_totals = {
        "regularSeason": {"gamesPlayed": 40, "wins": 20},
        "playoffs": {"gamesPlayed": 5, "wins": 3},
    }
    row = _build_career_row(player_id=1, career_totals=career_totals, position_code="G")
    assert row["rs_wins"] == 20
    assert row["po_wins"] == 3
    assert "rs_goals" not in row


def test_build_career_row_uses_skater_extractor_for_non_goalie_position():
    career_totals = {
        "regularSeason": {"goals": 10, "assists": 15},
        "playoffs": {},
    }
    row = _build_career_row(player_id=2, career_totals=career_totals, position_code="C")
    assert row["rs_goals"] == 10
    assert row["rs_assists"] == 15
    assert "rs_wins" not in row
