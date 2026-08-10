import pytest

from src import database


def _fake_post(response_body, captured=None):
    def fake_post(url, json=None, headers=None, timeout=None):
        if captured is not None:
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            captured["timeout"] = timeout

        class _FakeResponse:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return response_body

        return _FakeResponse()

    return fake_post


def test_execute_posts_to_v2_pipeline_with_bearer_auth(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        database.requests,
        "post",
        _fake_post(
            {"results": [
                {"type": "ok", "response": {"type": "execute", "result": {"cols": [], "rows": []}}},
                {"type": "ok", "response": {"type": "close"}},
            ]},
            captured,
        ),
    )

    client = database._TursoHttpClient("https://example-org.turso.io", "fake-token")
    client.execute("SELECT 1")

    assert captured["url"] == "https://example-org.turso.io/v2/pipeline"
    assert captured["headers"]["Authorization"] == "Bearer fake-token"
    assert captured["json"]["requests"][0]["type"] == "execute"
    assert captured["json"]["requests"][0]["stmt"]["sql"] == "SELECT 1"


def test_execute_encodes_positional_params(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        database.requests,
        "post",
        _fake_post(
            {"results": [
                {"type": "ok", "response": {"type": "execute", "result": {"cols": [], "rows": []}}},
                {"type": "ok", "response": {"type": "close"}},
            ]},
            captured,
        ),
    )

    client = database._TursoHttpClient("https://example-org.turso.io", "fake-token")
    client.execute("SELECT * FROM t WHERE id = ? AND name = ?", (1, "alice"))

    args = captured["json"]["requests"][0]["stmt"]["args"]
    assert args == [
        {"type": "integer", "value": "1"},
        {"type": "text", "value": "alice"},
    ]


def test_execute_encodes_none_and_float_params(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        database.requests,
        "post",
        _fake_post(
            {"results": [
                {"type": "ok", "response": {"type": "execute", "result": {"cols": [], "rows": []}}},
                {"type": "ok", "response": {"type": "close"}},
            ]},
            captured,
        ),
    )

    client = database._TursoHttpClient("https://example-org.turso.io", "fake-token")
    client.execute("SELECT ?, ?", (None, 1.5))

    args = captured["json"]["requests"][0]["stmt"]["args"]
    assert args == [
        {"type": "null"},
        {"type": "float", "value": 1.5},
    ]


def test_fetchall_decodes_rows_and_exposes_description(monkeypatch):
    monkeypatch.setattr(
        database.requests,
        "post",
        _fake_post({"results": [
            {"type": "ok", "response": {"type": "execute", "result": {
                "cols": [{"name": "id"}, {"name": "name"}],
                "rows": [
                    [{"type": "integer", "value": "1"}, {"type": "text", "value": "alice"}],
                    [{"type": "integer", "value": "2"}, {"type": "text", "value": "bob"}],
                ],
            }}},
            {"type": "ok", "response": {"type": "close"}},
        ]}),
    )

    client = database._TursoHttpClient("https://example-org.turso.io", "fake-token")
    cursor = client.execute("SELECT id, name FROM t")

    assert [d[0] for d in cursor.description] == ["id", "name"]
    assert cursor.fetchall() == [(1, "alice"), (2, "bob")]


def test_fetchone_returns_none_when_no_rows(monkeypatch):
    monkeypatch.setattr(
        database.requests,
        "post",
        _fake_post({"results": [
            {"type": "ok", "response": {"type": "execute", "result": {
                "cols": [{"name": "id"}], "rows": [],
            }}},
            {"type": "ok", "response": {"type": "close"}},
        ]}),
    )

    client = database._TursoHttpClient("https://example-org.turso.io", "fake-token")
    cursor = client.execute("SELECT id FROM t WHERE id = ?", (99,))

    assert cursor.fetchone() is None


def test_execute_raises_valueerror_on_hrana_error_response(monkeypatch):
    monkeypatch.setattr(
        database.requests,
        "post",
        _fake_post({"results": [
            {"type": "error", "error": {"message": "upstream forward failed"}},
        ]}),
    )

    client = database._TursoHttpClient("https://example-org.turso.io", "fake-token")

    with pytest.raises(ValueError, match="upstream forward failed"):
        client.execute("SELECT 1")
