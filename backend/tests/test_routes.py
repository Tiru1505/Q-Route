"""Tests for route optimization endpoints."""


def test_optimize_route_success(client, sample_route_request):
    response = client.post("/api/routes/optimize", json=sample_route_request)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "request_id" in data
    assert data["algorithm"] == "qpso"
    assert "route" in data
    assert data["route"]["distance_km"] > 0
    assert data["route"]["travel_time_minutes"] > 0
    assert len(data["route"]["coordinates"]) >= 2


def test_optimize_route_with_dijkstra(client):
    response = client.post("/api/routes/optimize", json={
        "source": {"lat": 17.385, "lon": 78.4867},
        "destination": {"lat": 17.450, "lon": 78.380},
        "algorithm": "dijkstra",
    })
    assert response.status_code == 200
    assert response.json()["algorithm"] == "dijkstra"


def test_optimize_route_default_algorithm(client):
    response = client.post("/api/routes/optimize", json={
        "source": {"lat": 17.385, "lon": 78.4867},
        "destination": {"lat": 17.450, "lon": 78.380},
    })
    assert response.status_code == 200
    assert response.json()["algorithm"] == "qpso"


def test_optimize_same_source_destination_rejected(client):
    response = client.post("/api/routes/optimize", json={
        "source": {"lat": 17.385, "lon": 78.486},
        "destination": {"lat": 17.385, "lon": 78.486},
    })
    assert response.status_code == 422


def test_optimize_invalid_latitude(client):
    response = client.post("/api/routes/optimize", json={
        "source": {"lat": 100, "lon": 78},
        "destination": {"lat": 17, "lon": 78},
    })
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_optimize_missing_destination(client):
    response = client.post("/api/routes/optimize", json={
        "source": {"lat": 17.385, "lon": 78.486},
    })
    assert response.status_code == 422


def test_alternatives_returns_list(client, sample_route_request):
    response = client.post("/api/routes/alternatives", json=sample_route_request)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_get_route_not_found(client):
    response = client.get("/api/routes/nonexistent-id")
    assert response.status_code == 404


def test_route_history(client):
    response = client.get("/api/routes/history")
    assert response.status_code == 200
    assert "results" in response.json()


def test_route_response_has_eta(client, sample_route_request):
    response = client.post("/api/routes/optimize", json=sample_route_request)
    assert response.status_code == 200
    data = response.json()
    # ETA may be None if estimation fails, but the field should exist
    assert "eta" in data


def test_route_response_has_execution_time(client, sample_route_request):
    response = client.post("/api/routes/optimize", json=sample_route_request)
    data = response.json()
    assert "execution_time_ms" in data
    assert data["execution_time_ms"] >= 0
