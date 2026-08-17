import app as app_module


def test_direct_hit_on_client_route_returns_index_html():
    client = app_module.app.test_client()
    resp = client.get("/players")
    assert resp.status_code == 200
    assert b"<div id=\"root\">" in resp.data


def test_unknown_client_route_also_returns_index_html():
    client = app_module.app.test_client()
    resp = client.get("/teams")
    assert resp.status_code == 200
    assert b"<div id=\"root\">" in resp.data


def test_unmatched_api_path_still_404s():
    client = app_module.app.test_client()
    resp = client.get("/api/does-not-exist")
    assert resp.status_code == 404


def test_unmatched_static_path_still_404s():
    client = app_module.app.test_client()
    resp = client.get("/static/does-not-exist.js")
    assert resp.status_code == 404
