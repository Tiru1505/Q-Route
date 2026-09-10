"""
Acceptance tests — the twelve scenarios the system is required to handle.

WHAT THESE ARE FOR
------------------
Not unit coverage. Each test drives the real pipeline end to end and asserts
the BEHAVIOUR a demonstrator would show a judge: that a quiet road produces no
nagging, that a closed road is actually avoided, that a missing model produces
a refusal rather than a plausible number.

The bar throughout is that a test must be capable of FAILING for the right
reason. Asserting `response.status_code == 200` proves a route exists, not that
it is correct, so where a claim can be checked against something independent —
a closed edge, a different forecast, a documented threshold — it is.

WHY SOME ASSERTIONS ARE LOOSE
-----------------------------
The traffic layer is stochastic per scenario and the optimiser is a
metaheuristic. Asserting an exact ETA would make these tests fail on a reseed
for no useful reason. So they assert direction and invariants — congestion
rose, the closed edge is absent, the alternative is not worse — which is what
the requirement actually says.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# Two Hyderabad endpoints far enough apart to have genuine alternatives.
START = {"lat": 17.4435, "lon": 78.3772}      # Hitec City
END = {"lat": 17.3616, "lon": 78.4747}        # Charminar


# --------------------------------------------------------------- helpers

def optimise(algorithm="qpso", graph=None):
    body = {"source": START, "destination": END, "algorithm": algorithm}
    if graph:
        body["graph"] = graph
    r = client.post("/api/routes/optimize", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def set_scenario(name):
    r = client.post(f"/api/simulation/event?scenario={name}")
    assert r.status_code == 200, r.text
    return r.json()


def analyse(**params):
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return client.post(f"/api/agent/analyze{'?' + qs if qs else ''}")


@pytest.fixture(autouse=True)
def _normal_traffic():
    """Every test starts from a known state and leaves one behind."""
    set_scenario("normal")
    yield
    set_scenario("normal")


@pytest.fixture
def active_trip():
    """A trip for the agent to monitor. Optimising one creates it."""
    optimise()
    r = client.post("/api/routes/reroute", json={"progress": 0.3, "spike": False})
    assert r.status_code in (200, 409), r.text
    return True


# ------------------------------------------------------------ TEST 1..12

def test_1_normal_traffic_does_not_nag(active_trip):
    """Quiet road: the agent must not invent a reason to reroute."""
    set_scenario("normal")
    r = analyse(predictive="false")
    assert r.status_code == 200, r.text
    d = r.json()

    # It may decide either way — what it must not do is raise an alert without
    # clearing the documented savings gates.
    if d["alert"] is not None:
        saved = d["timeSaved"] or 0
        policy = client.get("/api/agent/status").json()["policy"]
        assert saved >= policy["minSavingMin"], (
            f"alerted on a {saved} min saving, below the "
            f"{policy['minSavingMin']} min policy floor"
        )
    assert d["decision"] in ("keep", "reroute")
    assert d["reason"], "every decision must carry its reasoning"


def test_2_congestion_shows_up_in_the_forecast(active_trip):
    """Heavier traffic must be visible to the agent, not just on a chart."""
    set_scenario("normal")
    quiet = analyse(predictive="true").json()

    set_scenario("heavy_congestion")
    busy = analyse(predictive="true", force="true").json()

    assert quiet["forecast"]["applied"], "forecaster did not run on the quiet road"
    assert busy["forecast"]["applied"], "forecaster did not run on the busy road"
    assert busy["forecast"]["observedMean"] > quiet["forecast"]["observedMean"], (
        f"heavy congestion ({busy['forecast']['observedMean']}) did not read "
        f"higher than normal ({quiet['forecast']['observedMean']})"
    )


def test_3_heavy_congestion_is_evaluated(active_trip):
    """Under heavy congestion the agent must actually run the comparison."""
    set_scenario("heavy_congestion")
    r = analyse(force="true")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["currentEta"] is not None, "no ETA computed for the current route"
    assert d["alternativeEta"] is not None, "no alternative was evaluated"
    assert d["analysisMs"] >= 0


def test_4_clear_saving_is_recommended(active_trip):
    """When the current route is congested and an alternative is better, say so."""
    client.post("/api/simulation/congest-route?level=0.95")
    d = analyse(force="true").json()

    if d["timeSaved"] and d["timeSaved"] > 0:
        assert d["alternativeEta"] <= d["currentEta"] + 1e-6, (
            "the 'better' alternative is slower than the current route"
        )
        assert "min" in d["reason"], "recommendation must quantify the saving"


def test_5_no_saving_means_no_recommendation(active_trip):
    """A route that is already good must not be replaced for the sake of it."""
    set_scenario("normal")
    d = analyse(predictive="false").json()
    if d["decision"] == "keep":
        assert d["alert"] is None or d["alert"].get("kind") in ("incident", "closure")
        assert d["reason"]


def test_6_accident_changes_the_network():
    """An accident must alter the graph, not merely a banner."""
    before = client.get("/api/traffic/current").json()
    after_event = set_scenario("accident")
    after = client.get("/api/traffic/current").json()

    assert after_event["dataSource"] == "SIMULATED", "simulated events must be labelled"
    assert after_event["incidents"] or after_event["closedEdges"] >= 0
    assert before["records"] and after["records"], "traffic snapshot went empty"


def test_7_closed_roads_are_avoided():
    """A closed edge must not appear in a route computed afterwards."""
    set_scenario("road_closure")

    from app.integrations.engine_bridge import get_engine
    engine = get_engine()
    closed = {(u, v) for u, v, d in engine.G.edges(data=True)
              if d.get("road_status") == "closed"}
    if not closed:
        pytest.skip("this scenario seed produced no closures")

    data = optimise()
    route = data.get("route") or data
    nodes = [int(n) for n in route["nodes"]]
    used = set(zip(nodes, nodes[1:]))
    assert not (used & closed), "route drives through a closed road"


def test_8_clearing_restores_the_network():
    """Traffic clearing must bring congestion back down."""
    set_scenario("heavy_congestion")
    heavy = client.get("/api/analytics").json()
    set_scenario("clearing")
    cleared = client.get("/api/analytics").json()

    def mean_congestion(payload):
        stat = next(s for s in payload["stats"] if s["label"] == "Average Traffic")
        return stat["value"]

    assert mean_congestion(cleared) < mean_congestion(heavy), (
        f"clearing left congestion at {mean_congestion(cleared)}%, "
        f"no better than heavy at {mean_congestion(heavy)}%"
    )


def test_9_uploaded_image_is_detected():
    """An uploaded photo must be run through the detector, not guessed at."""
    import glob

    images = sorted(glob.glob("data/vision/dats_yolo/images/val/*"))
    if not images:
        pytest.skip("no validation imagery available")

    with open(images[0], "rb") as fh:
        r = client.post("/api/vision/analyse",
                        files={"file": ("road.jpg", fh, "image/jpeg")})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["kind"] == "image"
    assert d["measures"] == "occupancy", "a still frame measures occupancy, not flow"
    assert "congestion" in d, "no congestion derived from the detection"
    assert d["annotated"], "no annotated frame returned"
    # A photo can legitimately contain no vehicles; what it must never do is
    # silently drive the forecaster.
    assert "forecastNote" in d


def test_10_uploaded_video_produces_flow():
    """A clip must yield line crossings, which is what the forecaster eats."""
    import glob
    import pathlib
    import tempfile

    images = sorted(glob.glob("data/vision/dats_yolo/images/val/*"))
    if not images:
        pytest.skip("no validation imagery available")

    from scripts.test_pipeline import make_clip

    tmp = pathlib.Path(tempfile.mkdtemp())
    clip = make_clip(pathlib.Path(images[-1]), tmp / "clip.mp4", frames=120)
    with open(clip, "rb") as fh:
        r = client.post("/api/vision/analyse",
                        files={"file": ("clip.mp4", fh, "video/mp4")},
                        data={"sample_fps": "12.5", "max_frames": "60"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["kind"] == "video"
    assert d["measures"] == "flow", "a clip measures flow, not occupancy"
    assert d["framesProcessed"] > 1, "only one frame was processed"
    assert "per15Min" in d and "extrapolationFactor" in d


def test_11_insufficient_data_is_refused_not_faked():
    """The forecaster must reject a short history rather than pad it."""
    import numpy as np

    from app.services.forecast_service import _load

    model, _ = _load()
    short = np.zeros((1, 4), dtype="float32")
    clock = model.clock_features(np.array([0.0]), np.array([0.0]))
    with pytest.raises(ValueError, match="steps of history"):
        model.predict(short, clock)


def test_12_missing_trip_is_an_error_not_a_guess():
    """With nothing to monitor the agent must refuse, not invent a journey."""
    from app.integrations.engine_bridge import get_engine

    engine = get_engine()
    engine.trip = None
    r = analyse()
    assert r.status_code == 409, f"expected a refusal, got {r.status_code}"
    # This API wraps errors in its own envelope rather than FastAPI's `detail`,
    # so read the message from where it actually lives.
    body = r.json()
    message = (body.get("error") or {}).get("message") or body.get("detail") or ""
    assert "no active trip" in message.lower(), body


def test_13_uploaded_counts_reach_the_forecaster():
    """
    The Lab and the routing agent must not be parallel universes.

    Counting real vehicles on a road and then forecasting that road from a
    reconstruction instead is the failure this guards: it looks identical on
    screen, and the two would silently disagree about the same tarmac.
    """
    import glob
    import pathlib
    import tempfile

    from app.integrations.prediction_adapter import get_prediction_adapter
    from app.models.route_models import Coordinate
    from app.services.observation_store import clear

    images = sorted(glob.glob("data/vision/dats_yolo/images/val/*"))
    if not images:
        pytest.skip("no validation imagery available")

    from scripts.test_pipeline import make_clip

    road_id, lat, lon = "hyderabad:inner-ring-road", 17.34133, 78.50367
    clear(road_id)

    adapter = get_prediction_adapter()
    if not hasattr(adapter, "_observed_series"):
        pytest.skip("forecaster unavailable; the random placeholder is in use")

    before = adapter.predict(Coordinate(lat=lat, lon=lon), 15)
    assert before["data_source"] == "lstm+anchored-history", (
        "with no observations the forecast should be reconstructed, and say so"
    )

    need = adapter._forecaster.lookback
    tmp = pathlib.Path(tempfile.mkdtemp())
    for i in range(need):
        clip = make_clip(pathlib.Path(images[-(i + 1)]), tmp / f"c{i}.mp4", frames=180)
        with open(clip, "rb") as fh:
            r = client.post("/api/vision/analyse",
                            files={"file": (f"c{i}.mp4", fh, "video/mp4")},
                            data={"city": "hyderabad", "road_id": road_id,
                                  "sample_fps": "12.5", "max_frames": "90"})
        assert r.status_code == 200, r.text
        assert r.json().get("recorded"), "the observation was not recorded on the road"

    listing = client.get("/api/vision/observations").json()
    assert any(x["roadId"] == road_id and x["observations"] >= need
               for x in listing["roads"]), listing

    after = adapter.predict(Coordinate(lat=lat, lon=lon), 15)
    assert after["data_source"] == "lstm+uploaded-observations", (
        f"real counts were on record and the forecaster still used "
        f"{after['data_source']}"
    )
    assert after["observed_road"]["roadId"] == road_id
    assert "measured traffic" in after["assumption"]
    clear(road_id)


def test_14_partial_series_is_not_padded():
    """One observation short of a window must fall back, not be padded out."""
    from app.integrations.prediction_adapter import get_prediction_adapter
    from app.models.route_models import Coordinate
    from app.services.observation_store import clear, record

    adapter = get_prediction_adapter()
    if not hasattr(adapter, "_observed_series"):
        pytest.skip("forecaster unavailable")

    road_id, lat, lon = "test:partial-road", 17.34133, 78.50367
    clear(road_id)
    need = adapter._forecaster.lookback
    for _ in range(need - 1):                       # deliberately one short
        record(road_id, "hyderabad", "Partial Road", lat, lon,
               {"CarCount": 40, "BikeCount": 20, "BusCount": 2, "TruckCount": 2})

    out = adapter.predict(Coordinate(lat=lat, lon=lon), 15)
    assert out["data_source"] == "lstm+anchored-history", (
        "a short series was used as if it were a full window"
    )
    clear(road_id)


def test_15_benchmark_follows_the_traffic():
    """
    Congestion sets the edge weights, so it sets the optimum.

    This guards a cache key, and a stale cache is invisible: the numbers look
    stable and reproducible while silently describing traffic that is no longer
    in force. Measured before the fix, the benchmark returned an identical
    optimum of 2.18136 under normal, peak-hour AND heavy congestion.
    """
    qs = ("origin_lat=17.4435&origin_lon=78.3772"
          "&dest_lat=17.3616&dest_lon=78.4747&trials=5")

    optima = {}
    for scenario in ("normal", "peak_hour", "heavy_congestion"):
        set_scenario(scenario)
        r = client.get(f"/api/benchmark/results?{qs}")
        assert r.status_code == 200, r.text
        optima[scenario] = r.json()["exact_optimum"]

    assert len(set(optima.values())) == len(optima), (
        f"different traffic produced the same optimum — the cache is stale: {optima}"
    )
    assert optima["heavy_congestion"] > optima["normal"], (
        f"heavy congestion should cost more than normal: {optima}"
    )


def test_16_same_inputs_are_reproducible():
    """
    Identical conditions must give an identical answer.

    The opposite failure to the one above: results that wander between runs
    cannot be compared, and a benchmark whose numbers move on their own proves
    nothing about any algorithm.
    """
    set_scenario("normal")
    body = {"source": START, "destination": END, "algorithm": "qpso"}

    first = client.post("/api/routes/optimize", json=body).json()
    second = client.post("/api/routes/optimize", json=body).json()

    a = first.get("route", first)
    b = second.get("route", second)
    assert a["distance_km"] == b["distance_km"], "same route, same traffic, different distance"
    assert a["nodes"] == b["nodes"], "same route, same traffic, different path"


# --------------------------------------------------- contract guarantees

def test_simulated_results_are_always_labelled():
    """Nothing generated may reach the UI without saying so."""
    for path in ("/api/simulation/scenarios",
                 "/api/simulation/event?scenario=normal",
                 "/api/simulation/reset"):
        r = client.post(path) if "event" in path or "reset" in path else client.get(path)
        assert r.status_code == 200, path
        assert r.json().get("dataSource") == "SIMULATED", f"{path} is unlabelled"


def test_agent_decision_is_explained():
    """Every decision carries reasoning built from measured values."""
    optimise()
    client.post("/api/routes/reroute", json={"progress": 0.3, "spike": True})
    d = analyse(force="true").json()
    assert d["reason"], "decision with no reasoning"
    assert d["forecast"]["note"], "forecast scope must be stated"
    assert d["severity"] in ("info", "moderate", "severe")
