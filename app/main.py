"""SmartRoute AI Backend — FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.analytics import router as analytics_router
from app.api.health import router as health_router
from app.api.routes import router as routes_router
from app.api.alerts import router as alerts_router
from app.api.assistant import router as assistant_router
from app.api.benchmark import router as benchmark_router
from app.api.optimization import router as optimization_router
from app.api.places import router as places_router
from app.api.prediction import router as prediction_router
from app.api.traffic import router as traffic_router
from app.core.config import get_settings
from app.core.errors import SmartRouteError, domain_error_handler, validation_error_handler
from app.core.logging import setup_logging, get_logger


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown hooks
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan: initialise logging + database on startup, clean up on shutdown."""
    setup_logging()
    logger = get_logger("main")
    logger.info("SmartRoute AI Backend starting up …")

    from app.database.mongodb import startup_db, shutdown_db
    startup_db()

    # Warm the optimisation engine. Loading the 286,603-node Hyderabad graph
    # takes ~25 s; doing it here means the FIRST request is fast instead of
    # being the one that pays for it. Failure is non-fatal — the adapters fall
    # back to their mock implementations and the API still serves.
    try:
        from app.integrations.engine_bridge import get_engine
        engine = get_engine()
        logger.info(
            "Optimisation engine ready: %s nodes, %s edges",
            f"{engine.G.number_of_nodes():,}", f"{engine.G.number_of_edges():,}",
        )
    except Exception as exc:
        logger.warning("Engine unavailable, serving mock adapters: %s", exc)

    yield  # ← application runs here

    logger.info("SmartRoute AI Backend shutting down …")
    shutdown_db()


# ---------------------------------------------------------------------------
# Application instance
# ---------------------------------------------------------------------------

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "Integration API for the Quantum-Inspired Dynamic Traffic Route "
        "Optimization Platform (SIH26137). Provides route optimization, "
        "traffic data, prediction, benchmarking, and alert services for "
        "a React + Leaflet frontend."
    ),
    version=settings.app_version,
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    return validation_error_handler(request, exc)


@app.exception_handler(HTTPException)
async def handle_http_error(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": {"code": "http_error", "message": exc.detail}},
    )


@app.exception_handler(SmartRouteError)
async def handle_domain_error(request: Request, exc: SmartRouteError) -> JSONResponse:
    return domain_error_handler(request, exc)


@app.exception_handler(Exception)
async def handle_unhandled_error(_: Request, exc: Exception) -> JSONResponse:
    logger = get_logger("main")
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {"code": "internal_error", "message": "An unexpected error occurred"},
        },
    )


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def allow_private_network(request: Request, call_next):
    """
    Let an HTTPS page reach this API on localhost.

    Chrome's Private Network Access rules block a request from a public site to
    a private address — which includes localhost — unless the server explicitly
    opts in. The browser sends a preflight carrying
    Access-Control-Request-Private-Network: true and refuses the real request
    unless the response grants it. Without this, a frontend deployed on Vercel
    and pointed at http://localhost:8010 fails with an opaque CORS error even
    though the API is running and its origin list is correct.

    Only answered when the browser actually asks, and CORS still applies on top:
    this widens nothing on its own, because an origin outside ALLOWED_ORIGINS is
    still refused by the middleware above.
    """
    response = await call_next(request)
    if request.headers.get("access-control-request-private-network") == "true":
        response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(health_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(routes_router, prefix="/api")
app.include_router(places_router, prefix="/api")
app.include_router(optimization_router, prefix="/api")
app.include_router(traffic_router, prefix="/api")
app.include_router(prediction_router, prefix="/api")
app.include_router(benchmark_router, prefix="/api")
app.include_router(alerts_router, prefix="/api")
app.include_router(assistant_router, prefix="/api")
