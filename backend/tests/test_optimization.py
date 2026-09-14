"""Tests for optimization endpoints."""


def test_optimize_qpso(client, sample_optimization_request):
    response = client.post("/api/optimization/qpso", json=sample_optimization_request)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["result"]["algorithm"] == "qpso"


def test_optimize_pso(client, sample_optimization_request):
    response = client.post("/api/optimization/pso", json=sample_optimization_request)
    assert response.status_code == 200
    assert response.json()["result"]["algorithm"] == "pso"


def test_optimize_ga(client, sample_optimization_request):
    response = client.post("/api/optimization/ga", json=sample_optimization_request)
    assert response.status_code == 200
    assert response.json()["result"]["algorithm"] == "ga"


def test_optimize_dijkstra(client, sample_optimization_request):
    response = client.post("/api/optimization/dijkstra", json=sample_optimization_request)
    assert response.status_code == 200
    assert response.json()["result"]["algorithm"] == "dijkstra"


def test_optimize_invalid_algorithm(client, sample_optimization_request):
    response = client.post("/api/optimization/invalid_algo", json=sample_optimization_request)
    assert response.status_code == 422


def test_optimization_response_structure(client, sample_optimization_request):
    response = client.post("/api/optimization/qpso", json=sample_optimization_request)
    data = response.json()
    assert "result" in data
    assert "status" in data
    assert "best_fitness" in data
    assert "iterations_used" in data
    result = data["result"]
    assert "route" in result
    assert "execution_time_ms" in result
