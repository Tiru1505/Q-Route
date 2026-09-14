"""Tests for traffic endpoints."""


def test_current_traffic(client):
    response = client.get("/api/traffic/current")
    assert response.status_code == 200
    data = response.json()
    assert "records" in data
    assert "timestamp" in data


def test_update_traffic(client, sample_traffic_update):
    response = client.post("/api/traffic/update", json=sample_traffic_update)
    assert response.status_code == 200
    data = response.json()
    assert data["updated"] == 2


def test_update_traffic_empty_records(client):
    response = client.post("/api/traffic/update", json={"records": []})
    assert response.status_code == 422


def test_predict_traffic(client):
    response = client.get("/api/traffic/predict?lat=17.385&lon=78.4867&horizon_minutes=30")
    assert response.status_code == 200
    data = response.json()
    assert "predicted_congestion" in data
    assert "location" in data
    assert data["horizon_minutes"] == 30
    assert 0 <= data["predicted_congestion"] <= 1


def test_predict_traffic_invalid_lat(client):
    response = client.get("/api/traffic/predict?lat=200&lon=78&horizon_minutes=30")
    assert response.status_code == 422


def test_predict_traffic_default_horizon(client):
    response = client.get("/api/traffic/predict?lat=17.385&lon=78.4867")
    assert response.status_code == 200
    assert response.json()["horizon_minutes"] == 30


def test_prediction_status(client):
    response = client.get("/api/prediction/status")
    assert response.status_code == 200
    assert response.json()["status"] == "adapter_placeholder"
