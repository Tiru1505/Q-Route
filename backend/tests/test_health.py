"""Tests for system health and status endpoints."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_status_returns_version_and_environment() -> None:
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert "environment" in data
    assert "database" in data
    assert "adapters" in data


def test_route_optimization_reports_its_data_source() -> None:
    """
    Was test_route_optimization_uses_mock_adapter, back when every adapter was
    a placeholder. The services now default to the real OSM engine, so the
    assertion is inverted: the response must say which adapter produced it,
    and "mock" is exactly what we no longer want to see in a real run.
    """
    response = client.post(
        "/api/routes/optimize",
        json={
            "source": {"lat": 17.3850, "lon": 78.4867},
            "destination": {"lat": 17.4500, "lon": 78.3800},
            "algorithm": "qpso",
        },
    )
    assert response.status_code == 200
    assert response.json()["metadata"]["data_source"] == "osm"


def test_invalid_coordinates_use_consistent_error_shape() -> None:
    response = client.post(
        "/api/routes/optimize",
        json={
            "source": {"lat": 200, "lon": 78},
            "destination": {"lat": 17, "lon": 78},
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
