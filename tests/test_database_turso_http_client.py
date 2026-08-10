import requests
import pytest

from src import database


class _FakeSession:
    """Stand-in for requests.Session, tracking calls/lifecycle for assertions."""

    instances = []

    def __init__(self, post_fn=None, response_body=None):
        self._post_fn = post_fn
        self._response_body = response_body
        self.post_calls = []
        self.closed = False
        _FakeSession.instances.append(self)

    def post(self, url, json=None, headers=None, timeout=None):
        self.post_calls.append(
            {"url": url, "json": json, "headers": headers, "timeout": timeout}
        )
        if self._post_fn is not None:
            return self._post_fn(url, json=json, headers=headers, timeout=timeout)

        class _FakeResponse:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return self._response_body

        resp = _FakeResponse()
        resp._response_body = self._response_body
        return resp

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def _reset_fake_sessions():
    _FakeSession.instances = []
    yield
    _FakeSession.instances = []


def _patch_session(monkeypatch, response_body=None, post_fn=None):
    monkeypatch.setattr(
        database.requests, "Session",
        lambda: _FakeSession(post_fn=post_fn, response_body=response_body),
    )


_OK_EMPTY_RESULT = {"results": [
    {"type": "ok", "response": {"type": "execute", "result": {"cols": [], "rows": []}}},
    {"type": "ok", "response": {"type": "close"}},
]}


def test_execute_posts_to_v2_pipeline_with_bearer_auth(monkeypatch):
    _patch_session(monkeypatch, response_body=_OK_EMPTY_RESULT)

    client = database._TursoHttpClient("https://example-org.turso.io", "fake-token")
    client.execute("SELECT 1")

    call = _FakeSession.instances[0].post_calls[0]
    assert call["url"] == "https://example-org.turso.io/v2/pipeline"
    assert call["headers"]["Authorization"] == "Bearer fake-token"
    assert call["json"]["requests"][0]["type"] == "execute"
    assert call["json"]["requests"][0]["stmt"]["sql"] == "SELECT 1"


def test_execute_reuses_one_session_across_multiple_calls(monkeypatch):
    _patch_session(monkeypatch, response_body=_OK_EMPTY_RESULT)

    client = database._TursoHttpClient("https://example-org.turso.io", "fake-token")
    client.execute("SELECT 1")
    client.execute("SELECT 2")

    assert len(_FakeSession.instances) == 1
    assert len(_FakeSession.instances[0].post_calls) == 2


def test_close_closes_the_underlying_session(monkeypatch):
    _patch_session(monkeypatch, response_body=_OK_EMPTY_RESULT)

    client = database._TursoHttpClient("https://example-org.turso.io", "fake-token")
    client.execute("SELECT 1")
    client.close()

    assert _FakeSession.instances[0].closed is True


def test_execute_encodes_positional_params(monkeypatch):
    _patch_session(monkeypatch, response_body=_OK_EMPTY_RESULT)

    client = database._TursoHttpClient("https://example-org.turso.io", "fake-token")
    client.execute("SELECT * FROM t WHERE id = ? AND name = ?", (1, "alice"))

    args = _FakeSession.instances[0].post_calls[0]["json"]["requests"][0]["stmt"]["args"]
    assert args == [
        {"type": "integer", "value": "1"},
        {"type": "text", "value": "alice"},
    ]


def test_execute_encodes_none_and_float_params(monkeypatch):
    _patch_session(monkeypatch, response_body=_OK_EMPTY_RESULT)

    client = database._TursoHttpClient("https://example-org.turso.io", "fake-token")
    client.execute("SELECT ?, ?", (None, 1.5))

    args = _FakeSession.instances[0].post_calls[0]["json"]["requests"][0]["stmt"]["args"]
    assert args == [
        {"type": "null"},
        {"type": "float", "value": 1.5},
    ]


def test_fetchall_decodes_rows_and_exposes_description(monkeypatch):
    _patch_session(monkeypatch, response_body={"results": [
        {"type": "ok", "response": {"type": "execute", "result": {
            "cols": [{"name": "id"}, {"name": "name"}],
            "rows": [
                [{"type": "integer", "value": "1"}, {"type": "text", "value": "alice"}],
                [{"type": "integer", "value": "2"}, {"type": "text", "value": "bob"}],
            ],
        }}},
        {"type": "ok", "response": {"type": "close"}},
    ]})

    client = database._TursoHttpClient("https://example-org.turso.io", "fake-token")
    cursor = client.execute("SELECT id, name FROM t")

    assert [d[0] for d in cursor.description] == ["id", "name"]
    assert cursor.fetchall() == [(1, "alice"), (2, "bob")]


def test_fetchone_returns_none_when_no_rows(monkeypatch):
    _patch_session(monkeypatch, response_body={"results": [
        {"type": "ok", "response": {"type": "execute", "result": {
            "cols": [{"name": "id"}], "rows": [],
        }}},
        {"type": "ok", "response": {"type": "close"}},
    ]})

    client = database._TursoHttpClient("https://example-org.turso.io", "fake-token")
    cursor = client.execute("SELECT id FROM t WHERE id = ?", (99,))

    assert cursor.fetchone() is None


def test_execute_raises_valueerror_on_hrana_error_response(monkeypatch):
    _patch_session(monkeypatch, response_body={"results": [
        {"type": "error", "error": {"message": "upstream forward failed"}},
    ]})

    client = database._TursoHttpClient("https://example-org.turso.io", "fake-token")

    with pytest.raises(ValueError, match="upstream forward failed"):
        client.execute("SELECT 1")


def test_execute_raises_valueerror_on_empty_results(monkeypatch):
    _patch_session(monkeypatch, response_body={"results": []})

    client = database._TursoHttpClient("https://example-org.turso.io", "fake-token")

    with pytest.raises(ValueError, match="malformed"):
        client.execute("SELECT 1")


def test_execute_raises_valueerror_on_missing_result_key(monkeypatch):
    _patch_session(monkeypatch, response_body={"results": [
        {"type": "ok", "response": {"type": "execute"}},
    ]})

    client = database._TursoHttpClient("https://example-org.turso.io", "fake-token")

    with pytest.raises(ValueError, match="malformed"):
        client.execute("SELECT 1")


def test_execute_propagates_http_error_on_non_2xx_status(monkeypatch):
    def raising_post(url, json=None, headers=None, timeout=None):
        class _FakeResponse:
            status_code = 502

            def raise_for_status(self):
                raise requests.exceptions.HTTPError("502 Server Error")

        return _FakeResponse()

    _patch_session(monkeypatch, post_fn=raising_post)

    client = database._TursoHttpClient("https://example-org.turso.io", "fake-token")

    with pytest.raises(requests.exceptions.HTTPError):
        client.execute("SELECT 1")


def test_execute_propagates_connection_error(monkeypatch):
    def raising_post(url, json=None, headers=None, timeout=None):
        raise requests.exceptions.ConnectionError("connection refused")

    _patch_session(monkeypatch, post_fn=raising_post)

    client = database._TursoHttpClient("https://example-org.turso.io", "fake-token")

    with pytest.raises(requests.exceptions.ConnectionError):
        client.execute("SELECT 1")
