"""Time and date utility helpers."""

from datetime import datetime, timezone


def utc_now_iso() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def utc_now() -> datetime:
    """Return the current UTC datetime object."""
    return datetime.now(timezone.utc)


def format_duration(seconds: float) -> str:
    """Return a human-readable duration string."""
    if seconds < 1:
        return f"{seconds * 1000:.1f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    remaining = seconds % 60
    return f"{minutes}m {remaining:.0f}s"
