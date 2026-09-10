"""
Vehicle profiles — and the objective selector that shares their path.

WHAT THESE HOLD
---------------
The vehicle changes the ROUTE, not a label: a road the vehicle may not use
costs infinity, and time uses the slower of the road's speed and the vehicle's
top speed. The car changes nothing, so every route computed before vehicles
existed is reproduced exactly.

The objective (balanced / fastest / shortest / low congestion) travels the same
path. Until this change it never left the browser — the request builder took
it and did not send it — so it gets tested on the same terms: that the value
chosen is the value the backend routes by.
"""

from __future__ import annotations

import math
import pathlib
import re

import networkx as nx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from graph.edge_weights import MODES, CostModel, NoPathError, ObjectiveWeights
from graph.vehicles import DEFAULT_VEHICLE, VEHICLES, road_class, vehicle_profile

ROOT = pathlib.Path(__file__).resolve().parent.parent
client = TestClient(app)

HITEC = {"lat": 17.4435, "lon": 78.3772}
CHARMINAR = {"lat": 17.3616, "lon": 78.4747}
# A trip whose car route runs along the ORR, so an expressway ban has
# something to act on. Hitec City to Charminar never touches one.
GACHIBOWLI = {"lat": 17.443622, "lon": 78.351964}
SHAMSHABAD = {"lat": 17.257207, "lon": 78.345104}


def edge(highway="primary", length_m=1000.0, speed_kph=60.0, congestion=0.0, **extra):
    t = length_m / (speed_kph / 3.6)
    return {"highway": highway, "length_m": length_m, "free_flow_time_s": t,
            "current_time_s": t, "congestion": congestion, **extra}


def model(vehicle=None):
    return CostModel(weights=ObjectiveWeights.from_mode("balanced").normalised(),
                     ref_time_s=600.0, ref_distance_m=10_000.0,
                     **({"vehicle": vehicle_profile(vehicle)} if vehicle else {}))


# --------------------------------------------------------------- the rules

def test_the_car_changes_nothing():
    """The default model and an explicit car must price every edge identically."""
    default, car = model(), model("car")
    assert default.vehicle.id == DEFAULT_VEHICLE == "car"
    assert car.vehicle.neutral
    for e in (edge(), edge("motorway", 2500, 90), edge("residential", 200, 20, 0.6)):
        w = default.weights
        legacy = (w.time * e["current_time_s"] / 600.0
                  + w.distance * e["length_m"] / 10_000.0
                  + w.congestion * e["length_m"] * e["congestion"] / 10_000.0)
        assert default.edge_cost(e) == car.edge_cost(e) == pytest.approx(legacy)


def test_a_road_the_vehicle_may_not_use_costs_infinity():
    motorway, primary = edge("motorway"), edge("primary")
    assert math.isinf(model("bicycle").edge_cost(motorway))
    assert math.isfinite(model("bicycle").edge_cost(primary))
    assert math.isfinite(model("car").edge_cost(motorway))
    # OSMnx stores a list when it merged ways; the rule must still apply.
    assert math.isinf(model("bicycle").edge_cost(edge(["motorway", "trunk"])))


def test_top_speed_binds_only_where_the_road_is_faster():
    """In a jam everyone crawls at the jam's speed; on an open road the cap applies."""
    bike = model("bicycle")
    open_road = edge(length_m=1500, speed_kph=60)
    jammed = edge(length_m=1500, speed_kph=8)

    t_open, _, _ = bike.components(open_road)
    assert t_open == pytest.approx(1500 / (15 / 3.6)), "open road not capped at 15 km/h"
    t_jam, _, _ = bike.components(jammed)
    assert t_jam == pytest.approx(jammed["current_time_s"]), "the cap must not speed a jam up"


def test_no_permitted_route_is_its_own_error():
    """Two points joined only by an expressway: a car can go, a bicycle cannot."""
    G = nx.MultiDiGraph()
    G.add_edge("a", "b", **edge("motorway"))
    assert CostModel.calibrate(G, "a", "b", vehicle="car")
    with pytest.raises(NoPathError):
        CostModel.calibrate(G, "a", "b", vehicle="bicycle")


def test_the_api_reports_no_permitted_route_as_404_not_an_outage():
    from types import SimpleNamespace

    from app.core.errors import NoRouteFoundError
    from app.integrations.engine_bridge import _cost_model_for

    G = nx.MultiDiGraph()
    G.add_edge("a", "b", **edge("motorway"))
    fake = SimpleNamespace(G=G, scenario="t", graph_name="test-only-graph")
    with pytest.raises(NoRouteFoundError) as info:
        _cost_model_for(fake, "a", "b", vehicle="bicycle")
    assert info.value.status_code == 404
    assert "bicycle" in str(info.value.message)


# ----------------------------------------------------------- the contract

def test_unknown_vehicle_and_unknown_mode_are_rejected():
    for extra in ({"vehicle": "spaceship"}, {"mode": "scenic"}):
        r = client.post("/api/routes/optimize",
                        json={"source": HITEC, "destination": CHARMINAR, **extra})
        assert r.status_code == 422, (extra, r.status_code)


def test_the_request_accepts_exactly_the_cost_models_modes():
    """The Literal on RouteRequest restates MODES; this stops the two drifting."""
    from typing import get_args

    from app.models.route_models import RouteRequest

    assert set(get_args(RouteRequest.model_fields["mode"].annotation)) == set(MODES)


def test_the_vehicles_endpoint_is_the_table():
    body = client.get("/api/vehicles").json()
    assert [v["id"] for v in body["vehicles"]] == list(VEHICLES)
    assert body["default"] == DEFAULT_VEHICLE
    assumed = {v["id"] for v in body["vehicles"] if v["assumption"]}
    assert assumed == set(VEHICLES) - {"car"}, "every non-car rule is an assumption and must say so"
    assert "assumption" in body["note"].lower()


def test_the_offline_demo_list_matches_the_table():
    """mockData.js keeps a copy for the backend-less demo. It must not drift."""
    js = (ROOT / "frontend" / "src" / "data" / "mockData.js").read_text(encoding="utf-8")
    block = js[js.index("export const MOCK_VEHICLES"):]
    block = block[:block.index("\n}\n")]
    assert re.findall(r"id: '([a-z_]+)'", block) == list(VEHICLES)


# --------------------------------------------------- end to end, real graph

def _route(body):
    r = client.post("/api/routes/optimize", json={"algorithm": "dijkstra", **body})
    assert r.status_code == 200, r.text
    return r.json()


def test_the_objective_reaches_the_backend():
    """It never did: every route was 'balanced' whatever the user chose."""
    from app.integrations.engine_bridge import get_engine

    d = _route({"source": HITEC, "destination": CHARMINAR, "mode": "shortest"})
    assert d["metadata"]["mode"] == "shortest"
    assert get_engine().cost_model.mode == "shortest", "the route was not priced by the chosen objective"


def test_a_bicycle_is_kept_off_the_expressway_the_car_takes():
    from app.integrations.engine_bridge import get_engine

    G = get_engine().G
    car = _route({"source": GACHIBOWLI, "destination": SHAMSHABAD, "vehicle": "car"})
    car_model = get_engine().cost_model

    def expressway_hops(route, cm):
        nodes = [int(n) for n in route["route"]["nodes"]]
        return sum(road_class(cm.best_edge(G, u, v)[0]) in ("motorway", "motorway_link")
                   for u, v in zip(nodes, nodes[1:]))

    car_hops = expressway_hops(car, car_model)
    assert car_hops > 0, "the car no longer uses the ORR here — pick a trip that does, or this proves nothing"

    bike = _route({"source": GACHIBOWLI, "destination": SHAMSHABAD, "vehicle": "bicycle"})
    bike_model = get_engine().cost_model
    assert bike["metadata"]["vehicle"] == "bicycle"
    assert bike_model.vehicle.id == "bicycle", "the trip — and so any reroute — lost the vehicle"
    assert expressway_hops(bike, bike_model) == 0, "a bicycle was routed onto an expressway"
    assert bike["route"]["travel_time_minutes"] > car["route"]["travel_time_minutes"]


def test_qpso_does_not_reuse_another_vehicles_search():
    """
    QPSO caches a decoder holding the cost model. Keyed without the vehicle, a
    truck's search reused a car's; keyed without the graph, a pair of node ids
    shared by two networks reused the other network's.
    """
    from app.integrations import engine_bridge

    _route({"source": HITEC, "destination": CHARMINAR, "vehicle": "truck"})  # warm
    r = client.post("/api/routes/optimize", json={
        "source": HITEC, "destination": CHARMINAR, "algorithm": "qpso", "vehicle": "truck"})
    assert r.status_code == 200, r.text
    keys = [k for k in engine_bridge._decoders if "truck" in k]
    assert keys, f"no decoder keyed by vehicle: {list(engine_bridge._decoders)[:3]}"
    assert all(k[0] == "hyderabad" for k in keys), "decoder key does not name the graph"
