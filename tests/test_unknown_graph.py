"""
A road network that does not exist is a bad request — everywhere.

An unknown graph name used to produce a different wrong answer depending on
which endpoint received it:

    /routes/optimize          503  "graph unavailable" — a typo reported as an outage
    /simulation/scenarios     500  "an unexpected error occurred" — the cause hidden
    /optimization/{algo}      500  "optimization failed" — the optimiser blamed
    /routes/alternatives      404  "no route found" — a typo reported as a result
    /agent/status             200  the error tucked inside a success
    /places/search            200  results from every city — the filter ignored
    /monitor/start            200  and started a background loop that failed
                                   every tick for as long as it was left running

The cause was one bare KeyError handled however each caller happened to. It is
now UnknownGraphError, answered by one handler as 422 with the valid names.

The sweep below reads the endpoint list from the OpenAPI schema rather than
naming endpoints, so one added later that accepts a graph is covered without
anyone remembering to add it here. That is the regression this guards: the
next endpoint quietly doing what these seven did.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

BOGUS = "atlantis"

# Values for any OTHER required parameter, so a request fails on the graph and
# not on something missing. An endpoint needing a parameter not listed here
# fails the sweep with a message saying so, rather than passing by accident.
SAMPLE_QUERY = {"scenario": "normal"}
SAMPLE_BODY = {
    "source": {"lat": 17.4435, "lon": 78.3772},
    "destination": {"lat": 17.3616, "lon": 78.4747},
    "algorithm": "dijkstra",
    "question": "help",
}
PATH_PARAMS = {"algorithm": "dijkstra"}


def _graph_endpoints():
    spec = app.openapi()
    schemas = spec.get("components", {}).get("schemas", {})
    found = []
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            params = op.get("parameters", [])
            in_query = any(p["name"] == "graph" and p["in"] == "query" for p in params)
            ref = (op.get("requestBody", {}).get("content", {})
                     .get("application/json", {}).get("schema", {}).get("$ref"))
            body_schema = schemas.get(ref.split("/")[-1], {}) if ref else {}
            in_body = "graph" in body_schema.get("properties", {})
            if in_query or in_body:
                found.append((method.upper(), path, params, body_schema, in_query))
    return found


ENDPOINTS = _graph_endpoints()


def test_the_sweep_finds_the_endpoints():
    """A sweep that matched nothing would pass vacuously."""
    assert len(ENDPOINTS) >= 15, [e[1] for e in ENDPOINTS]


@pytest.mark.parametrize(
    "method,path,params,body_schema,in_query",
    ENDPOINTS,
    ids=[f"{m} {p}" for m, p, *_ in ENDPOINTS],
)
def test_unknown_graph_is_rejected(method, path, params, body_schema, in_query):
    url = path
    for name, value in PATH_PARAMS.items():
        url = url.replace("{" + name + "}", value)
    assert "{" not in url, f"{path}: add a sample path parameter to PATH_PARAMS"

    query = {}
    if in_query:
        query["graph"] = BOGUS
    for p in params:
        if p["in"] == "query" and p.get("required") and p["name"] != "graph":
            assert p["name"] in SAMPLE_QUERY, (
                f"{path} requires ?{p['name']} — add a sample to SAMPLE_QUERY"
            )
            query[p["name"]] = SAMPLE_QUERY[p["name"]]

    body = None
    if body_schema:
        body = dict(SAMPLE_BODY, graph=BOGUS)
        missing = [f for f in body_schema.get("required", []) if f not in body]
        assert not missing, f"{path} requires {missing} — add them to SAMPLE_BODY"

    with TestClient(app) as client:
        try:
            r = client.request(method, url, params=query, json=body)
        finally:
            # If the monitor regresses it starts a real background loop. Stop
            # it whatever happened, so a failure here cannot leak into the
            # tests that follow.
            if path.endswith("/monitor/start"):
                client.post("/api/monitor/stop")

    assert r.status_code == 422, f"{method} {path} -> {r.status_code}: {r.text[:200]}"
    err = r.json()["error"]
    assert err["code"] == "unknown_graph", err
    assert BOGUS in err["message"] and '"' not in err["message"][:1], err["message"]
    assert "hyderabad" in err["known"], "the valid names must travel with the error"


def test_a_known_graph_that_is_not_built_is_still_a_server_problem(monkeypatch):
    """
    Unknown and unavailable are different faults and must stay different.

    A name in the registry whose file has not been built is the server's
    problem — a client cannot fix it by retyping. That stays a 5xx.
    """
    from pathlib import Path

    import graph.graph_loader as gl

    fake = dict(gl.GRAPHS["pune"], path=Path("does/not/exist.pkl"))
    monkeypatch.setitem(gl.GRAPHS, "pune", fake)

    with pytest.raises(FileNotFoundError):
        gl.graph_path("pune")

    from graph.errors import UnknownGraphError

    with pytest.raises(UnknownGraphError):
        gl.graph_path(BOGUS)
    assert not issubclass(FileNotFoundError, UnknownGraphError)
