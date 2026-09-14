"""MongoDB collection definitions, index creation, and accessor helpers."""

from pymongo.collection import Collection
from pymongo.database import Database

from app.database.mongodb import get_database

# ---------------------------------------------------------------------------
# Collection names (single source of truth)
# ---------------------------------------------------------------------------

COLLECTIONS = (
    "users",
    "route_requests",
    "optimization_results",
    "traffic_records",
    "benchmark_results",
    "alerts",
    "trips",
)


# ---------------------------------------------------------------------------
# Index creation
# ---------------------------------------------------------------------------

def ensure_indexes(database: Database) -> None:
    """Create indexes for all application collections.

    Safe to call repeatedly — MongoDB skips indexes that already exist.
    """
    database.route_requests.create_index("created_at")
    database.route_requests.create_index("user_id")
    database.optimization_results.create_index("request_id", unique=True)
    database.traffic_records.create_index([("location.lat", 1), ("location.lon", 1)])
    database.traffic_records.create_index("recorded_at")
    database.benchmark_results.create_index("created_at")
    database.alerts.create_index([("user_id", 1), ("created_at", -1)])
    database.alerts.create_index("expires_at", expireAfterSeconds=0)
    # One document per Google account. Sparse, so users created any other way
    # (which have no google_sub) are not forced to share a null key.
    database.users.create_index("google_sub", unique=True, sparse=True)
    # One account per email. Wrapped: a database that already holds two
    # accounts with one email must not stop the server starting — sign-in
    # still works, and the duplicate check in the service still applies.
    try:
        database.users.create_index("email", unique=True, sparse=True)
    except Exception as exc:  # pragma: no cover - depends on existing data
        import logging

        logging.getLogger("database").warning("users.email index not created: %s", exc)
    # A user's trips, newest first — what the History page reads.
    database.trips.create_index([("user_id", 1), ("created_at", -1)])


# ---------------------------------------------------------------------------
# Collection accessors
# ---------------------------------------------------------------------------

def get_route_requests_col() -> Collection:
    return get_database()["route_requests"]


def get_optimization_results_col() -> Collection:
    return get_database()["optimization_results"]


def get_traffic_records_col() -> Collection:
    return get_database()["traffic_records"]


def get_benchmark_results_col() -> Collection:
    return get_database()["benchmark_results"]


def get_alerts_col() -> Collection:
    return get_database()["alerts"]


def get_users_col() -> Collection:
    return get_database()["users"]


def get_trips_col() -> Collection:
    return get_database()["trips"]
