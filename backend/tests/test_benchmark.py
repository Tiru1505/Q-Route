"""Tests for benchmark endpoints."""


def test_run_benchmark(client, sample_benchmark_request):
    response = client.post("/api/benchmark/run", json=sample_benchmark_request)
    assert response.status_code == 200
    data = response.json()
    assert "benchmark_id" in data
    assert "results" in data
    assert len(data["results"]) == 3  # dijkstra, pso, qpso


def test_benchmark_result_structure(client, sample_benchmark_request):
    response = client.post("/api/benchmark/run", json=sample_benchmark_request)
    data = response.json()
    for result in data["results"]:
        assert "algorithm" in result
        assert "status" in result
        assert "execution_time_ms" in result


def test_benchmark_results_history(client):
    response = client.get("/api/benchmark/results")
    assert response.status_code == 200
    assert "results" in response.json()


def test_benchmark_convergence(client):
    response = client.get("/api/benchmark/convergence?algorithm=qpso")
    assert response.status_code == 200
    data = response.json()
    assert data["algorithm"] == "qpso"
    assert "iterations" in data
    assert "fitness_values" in data
    assert len(data["iterations"]) == len(data["fitness_values"])
