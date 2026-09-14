"""Domain exception classes and FastAPI error handlers."""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


# ---------------------------------------------------------------------------
# Domain exceptions
# ---------------------------------------------------------------------------

class SmartRouteError(Exception):
    """Base class for all SmartRoute domain errors."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str = "An unexpected error occurred"):
        self.message = message
        super().__init__(self.message)


class GraphUnavailableError(SmartRouteError):
    status_code = 503
    code = "graph_unavailable"

    def __init__(self, message: str = "Road network graph is not available"):
        super().__init__(message)


class NoRouteFoundError(SmartRouteError):
    status_code = 404
    code = "no_route_found"

    def __init__(self, message: str = "No route could be found between the given points"):
        super().__init__(message)


class OptimizationError(SmartRouteError):
    status_code = 500
    code = "optimization_error"

    def __init__(self, message: str = "Optimization algorithm failed"):
        super().__init__(message)


class InvalidAlgorithmError(SmartRouteError):
    status_code = 422
    code = "invalid_algorithm"

    def __init__(self, algorithm: str):
        super().__init__(f"Unsupported algorithm: {algorithm}")


class TrafficDataUnavailableError(SmartRouteError):
    status_code = 503
    code = "traffic_data_unavailable"

    def __init__(self, message: str = "Traffic data is currently unavailable"):
        super().__init__(message)


class PredictionError(SmartRouteError):
    status_code = 500
    code = "prediction_error"

    def __init__(self, message: str = "Traffic prediction failed"):
        super().__init__(message)


class DatabaseUnavailableError(SmartRouteError):
    status_code = 503
    code = "database_unavailable"

    def __init__(self, message: str = "MongoDB is not reachable"):
        super().__init__(message)


class RequestTimeoutError(SmartRouteError):
    status_code = 504
    code = "timeout"

    def __init__(self, message: str = "The request timed out"):
        super().__init__(message)


class InvalidRouteError(SmartRouteError):
    status_code = 422
    code = "invalid_route"

    def __init__(self, message: str = "The computed route is invalid"):
        super().__init__(message)


# ---------------------------------------------------------------------------
# FastAPI error handlers
# ---------------------------------------------------------------------------

def _sanitize_errors(errors: list[dict]) -> list[dict]:
    """Make Pydantic error dicts JSON-safe by converting non-serialisable ctx values."""
    safe: list[dict] = []
    for err in errors:
        entry = {k: v for k, v in err.items() if k != "ctx"}
        if "ctx" in err:
            entry["ctx"] = {k: str(v) for k, v in err["ctx"].items()}
        safe.append(entry)
    return safe


def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"success": False, "error": {"code": "validation_error", "details": _sanitize_errors(exc.errors())}},
    )


def domain_error_handler(_: Request, exc: SmartRouteError) -> JSONResponse:
    """Handle any SmartRouteError subclass with a consistent JSON envelope."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": {"code": exc.code, "message": exc.message}},
    )
