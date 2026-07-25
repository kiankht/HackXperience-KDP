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
    assert response.headers["cache-control"] == "no-store, max-age=0"


def test_frontend_browser_routes_reopen_relay() -> None:
    response = client.get("/assignments/current")

    assert response.status_code == 200
    assert "Relay" in response.text
    assert response.headers["cache-control"] == "no-store, max-age=0"


def test_unknown_api_route_remains_a_json_404() -> None:
    response = client.get("/api/not-a-real-endpoint")

    assert response.status_code == 404
    assert response.json() == {"detail": "API endpoint not found."}


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
