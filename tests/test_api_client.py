from src import api_client


def test_get_season_games_builds_correct_url(monkeypatch):
    captured = {}

    def fake_get(url):
        captured["url"] = url
        return {"data": [{"id": 1}], "total": 1}

    monkeypatch.setattr(api_client, "_get", fake_get)
    result = api_client.get_season_games("20242025", 2)

    assert "season=20242025" in captured["url"]
    assert "gameType=2" in captured["url"]
    assert result == [{"id": 1}]


def test_get_play_by_play_builds_correct_url(monkeypatch):
    captured = {}

    def fake_get(url):
        captured["url"] = url
        return {"plays": []}

    monkeypatch.setattr(api_client, "_get", fake_get)
    result = api_client.get_play_by_play(2024020001)

    assert captured["url"] == "https://api-web.nhle.com/v1/gamecenter/2024020001/play-by-play"
    assert result == {"plays": []}


def test_get_shift_chart_builds_correct_url(monkeypatch):
    captured = {}

    def fake_get(url):
        captured["url"] = url
        return {"data": [{"id": 1, "playerId": 100}]}

    monkeypatch.setattr(api_client, "_get", fake_get)
    result = api_client.get_shift_chart(2024020001)

    assert "gameId=2024020001" in captured["url"]
    assert result == [{"id": 1, "playerId": 100}]
