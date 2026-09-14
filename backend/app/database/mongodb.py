"""MongoDB connection lifecycle management."""

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ConnectionFailure

from app.core.config import get_settings
from app.core.logging import get_logger

_client: MongoClient | None = None
_logger = get_logger("database")


def get_database() -> Database:
    """Return the application database handle, creating the client on first call."""
    global _client
    settings = get_settings()
    if _client is None:
        _client = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)
    return _client[settings.mongodb_database]


def close_database() -> None:
    """Close the MongoDB client connection."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
        _logger.info("MongoDB connection closed")


def startup_db() -> None:
    """Initialise the database connection and create indexes.

    Called once during the FastAPI lifespan startup phase.
    """
    from app.database.collections import ensure_indexes

    db = get_database()
    try:
        db.command("ping")
        _logger.info("MongoDB connection established — database: %s", db.name)
    except ConnectionFailure:
        _logger.warning(
            "MongoDB is not reachable; the application will start but database "
            "operations will fail until the connection is restored."
        )
        return

    ensure_indexes(db)
    _logger.info("MongoDB indexes ensured")


def shutdown_db() -> None:
    """Cleanly tear down the database connection.

    Called once during the FastAPI lifespan shutdown phase.
    """
    close_database()


def check_health() -> dict[str, str]:
    """Quick connectivity check used by the /status endpoint."""
    try:
        db = get_database()
        db.command("ping")
        return {"mongodb": "connected", "database": db.name}
    except Exception as exc:
        return {"mongodb": "disconnected", "error": str(exc)}
