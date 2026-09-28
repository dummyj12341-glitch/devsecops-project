"""Unit tests for the Notes API."""


def test_health_returns_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_notes_empty_at_start(client):
    resp = client.get("/notes")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_create_note(client):
    resp = client.post("/notes", json={"text": "buy milk"})
    assert resp.status_code == 201
    assert resp.get_json() == {"id": 1, "text": "buy milk"}


def test_created_note_is_listed(client):
    client.post("/notes", json={"text": "first"})
    client.post("/notes", json={"text": "second"})
    resp = client.get("/notes")
    assert [n["text"] for n in resp.get_json()] == ["first", "second"]


def test_create_note_without_text_is_rejected(client):
    resp = client.post("/notes", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_note_with_blank_text_is_rejected(client):
    resp = client.post("/notes", json={"text": "   "})
    assert resp.status_code == 400


def test_unknown_route_returns_404(client):
    assert client.get("/does-not-exist").status_code == 404
