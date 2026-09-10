"""Shared test fixtures and configuration."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """Return a FastAPI TestClient instance."""
    return TestClient(app)


@pytest.fixture
def sample_route_request() -> dict:
    """Return a sample route optimisation request body."""
    return {
        "source": {"lat": 17.3850, "lon": 78.4867},
        "destination": {"lat": 17.4500, "lon": 78.3800},
        "algorithm": "qpso",
    }


@pytest.fixture
def sample_optimization_request() -> dict:
    """Return a sample optimization request body."""
    return {
        "source": {"lat": 17.3850, "lon": 78.4867},
        "destination": {"lat": 17.4500, "lon": 78.3800},
        "algorithm": "qpso",
        "iterations": 50,
        "particles": 20,
    }


@pytest.fixture
def sample_benchmark_request(sample_route_request) -> dict:
    """Return a sample benchmark request body."""
    return {
        "route": sample_route_request,
        "algorithms": ["dijkstra", "pso", "qpso"],
        "repetitions": 1,
    }


@pytest.fixture
def sample_traffic_update() -> dict:
    """Return a sample traffic update body."""
    return {
        "records": [
            {"location": {"lat": 17.385, "lon": 78.4867}, "congestion": 0.65},
            {"location": {"lat": 17.410, "lon": 78.4500}, "congestion": 0.40},
        ]
    }


