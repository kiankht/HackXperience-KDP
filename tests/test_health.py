from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_health_identifies_relay() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "Relay"}


def test_root_serves_relay_frontend() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Relay" in response.text
    assert 'id="app"' in response.text
    assert "/static/app.js" in response.text
    assert "/static/style.css" in response.text


def test_frontend_assets_serve_complete_demo_flow() -> None:
    script = client.get("/static/app.js")
    stylesheet = client.get("/static/style.css")

    assert script.status_code == 200
    assert stylesheet.status_code == 200
    assert 'apiRequest("/api/demo/reset"' in script.text
    assert "Fill Incomplete Example" in script.text
    assert "Your work has been accepted and passed forward." in script.text
    assert "Work passed to you" in script.text
    assert ".handoff-flow" in stylesheet.text
    assert ".context-section" in stylesheet.text
