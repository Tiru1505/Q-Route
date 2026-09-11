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




# --------------------------------------------------------------- signing in
#
# The feature suites were written before sign-in existed and test features,
# not access: they call control endpoints (simulation, monitor, benchmark)
# with no session. Every test therefore runs signed in as an admin — unless
# it is marked `real_auth`, in which case the real checks apply. Access
# control has its own suites (test_rbac.py, test_trips.py) that are.

from app.core.security import SessionUser, current_user, require_admin  # noqa: E402

TEST_ADMIN = SessionUser(id="test-admin", email="admin@test.local",
                         name="Test Admin", role="admin")


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "real_auth: use the real session checks instead of the test admin")


@pytest.fixture(autouse=True)
def _signed_in_as_admin(request):
    if request.node.get_closest_marker("real_auth"):
        yield
        return
    app.dependency_overrides[current_user] = lambda: TEST_ADMIN
    app.dependency_overrides[require_admin] = lambda: TEST_ADMIN
    yield
    app.dependency_overrides.pop(current_user, None)
    app.dependency_overrides.pop(require_admin, None)


@pytest.fixture
def memory_db(monkeypatch):
    """
    In-memory `users` and `trips` collections, so account and trip tests never
    write into the real database. (An earlier auth test did, and the test user
    had to be deleted by hand.)
    """
    cols = {"users": FakeCollection(unique=("email",)), "trips": FakeCollection()}
    monkeypatch.setattr("app.database.collections.get_users_col", lambda: cols["users"])
    monkeypatch.setattr("app.database.collections.get_trips_col", lambda: cols["trips"])
    # Real-strength hashing costs ~0.4 s per password; the tests check the
    # logic, not the work factor.
    monkeypatch.setattr("app.core.security.PBKDF2_ITERATIONS", 1_000)
    return cols


# ------------------------------------------------- in-memory collections
#
# Only what the account and trip services use: find_one / find (with sort and
# limit) / insert_one / update_one / update_many / count_documents, equality
# filters, and the $set / $unset / $push / $inc update operators.

import copy  # noqa: E402
from types import SimpleNamespace  # noqa: E402

from bson import ObjectId  # noqa: E402


class DuplicateKeyError(Exception):
    """Named like pymongo's, and its message says 'duplicate', as the service checks."""


def _matches(doc: dict, flt: dict) -> bool:
    return all(doc.get(k) == v for k, v in flt.items())


class _Cursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, key, direction=1):
        self._docs.sort(key=lambda d: (d.get(key) is None, d.get(key)), reverse=direction < 0)
        return self

    def limit(self, n):
        self._docs = self._docs[:n]
        return self

    def __iter__(self):
        return iter(copy.deepcopy(self._docs))


class FakeCollection:
    def __init__(self, unique: tuple[str, ...] = ()):
        self.docs: list[dict] = []
        self.unique = unique

    def find_one(self, flt=None):
        for d in self.docs:
            if _matches(d, flt or {}):
                return copy.deepcopy(d)
        return None

    def find(self, flt=None):
        return _Cursor([d for d in self.docs if _matches(d, flt or {})])

    def count_documents(self, flt=None):
        return sum(_matches(d, flt or {}) for d in self.docs)

    def insert_one(self, doc):
        doc = copy.deepcopy(doc)
        doc.setdefault("_id", ObjectId())
        for key in self.unique:
            if doc.get(key) is not None and any(d.get(key) == doc[key] for d in self.docs):
                raise DuplicateKeyError(f"E11000 duplicate key error: {key}")
        self.docs.append(doc)
        return SimpleNamespace(inserted_id=doc["_id"])

    def _apply(self, d, update):
        for k, v in update.get("$set", {}).items():
            d[k] = copy.deepcopy(v)
        for k in update.get("$unset", {}):
            d.pop(k, None)
        for k, v in update.get("$push", {}).items():
            d.setdefault(k, []).append(copy.deepcopy(v))
        for k, v in update.get("$inc", {}).items():
            d[k] = d.get(k, 0) + v

    def update_one(self, flt, update, upsert=False):
        for d in self.docs:
            if _matches(d, flt):
                self._apply(d, update)
                return SimpleNamespace(matched_count=1)
        return SimpleNamespace(matched_count=0)

    def update_many(self, flt, update):
        hits = [d for d in self.docs if _matches(d, flt)]
        for d in hits:
            self._apply(d, update)
        return SimpleNamespace(matched_count=len(hits))
