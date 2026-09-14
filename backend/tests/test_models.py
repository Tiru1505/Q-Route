"""Tests for Pydantic model validation."""

import pytest
from pydantic import ValidationError

from app.models.route_models import Coordinate, RouteRequest, Algorithm
from app.models.traffic_models import TrafficRecord, TrafficUpdate
from app.models.benchmark_models import BenchmarkRequest
from app.models.alert_models import AlertType, AlertSeverity


class TestCoordinate:
    def test_valid_coordinate(self):
        c = Coordinate(lat=17.385, lon=78.4867)
        assert c.lat == 17.385

    def test_lat_out_of_range(self):
        with pytest.raises(ValidationError):
            Coordinate(lat=100, lon=78)

    def test_lon_out_of_range(self):
        with pytest.raises(ValidationError):
            Coordinate(lat=17, lon=200)


class TestRouteRequest:
    def test_valid_request(self):
        req = RouteRequest(
            source=Coordinate(lat=17.385, lon=78.4867),
            destination=Coordinate(lat=17.450, lon=78.380),
        )
        assert req.algorithm == "qpso"  # default

    def test_same_source_destination_raises(self):
        with pytest.raises(ValidationError, match="source and destination must be different"):
            RouteRequest(
                source=Coordinate(lat=17.385, lon=78.486),
                destination=Coordinate(lat=17.385, lon=78.486),
            )

    def test_all_algorithms_valid(self):
        for algo in Algorithm:
            req = RouteRequest(
                source=Coordinate(lat=17.385, lon=78.4867),
                destination=Coordinate(lat=17.450, lon=78.380),
                algorithm=algo,
            )
            assert req.algorithm == algo.value


class TestTrafficModels:
    def test_valid_traffic_record(self):
        r = TrafficRecord(
            location=Coordinate(lat=17.385, lon=78.486),
            congestion=0.5,
        )
        assert r.congestion == 0.5

    def test_congestion_out_of_range(self):
        with pytest.raises(ValidationError):
            TrafficRecord(
                location=Coordinate(lat=17.385, lon=78.486),
                congestion=1.5,
            )

    def test_traffic_update_empty_records(self):
        with pytest.raises(ValidationError):
            TrafficUpdate(records=[])


class TestAlertModels:
    def test_alert_type_enum(self):
        assert AlertType.congestion.value == "congestion"

    def test_severity_enum(self):
        assert AlertSeverity.critical.value == "critical"

