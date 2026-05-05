"""FastAPI application factory for FastAPI Template"""

import asyncio

# Load environment variables FIRST, before any other imports
# This ensures libraries can access env vars
from dotenv import load_dotenv
import os

# Load .env file from the project root
load_dotenv()

import logging
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta
from typing import Dict, Any
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi

from app.config import settings
from app.database import database_manager, init_db, close_db
from app.exceptions import setup_exception_handlers
from app.middleware.security import SecurityHeadersMiddleware
from app.middleware.logging import LoggingMiddleware
from app.middleware.rate_limiting import RateLimitingMiddleware
from app.api.v1.router import api_router

# Configure structured logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format=(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        if settings.log_format == "text"
        else '{"timestamp": "%(asctime)s", "name": "%(name)s", "level": "%(levelname)s", "message": "%(message)s"}'
    ),
)
logger = logging.getLogger(__name__)


def _next_weekly_standings_refresh(now: datetime) -> datetime:
    target = now.replace(hour=1, minute=0, second=0, microsecond=0)
    days_until_tuesday = (1 - now.weekday()) % 7
    target = target + timedelta(days=days_until_tuesday)
    if target <= now:
        target += timedelta(days=7)
    return target


async def _weekly_standings_refresh_loop() -> None:
    timezone_name = settings.fantacalcio_auto_refresh_timezone
    timezone = ZoneInfo(timezone_name)

    while True:
        now = datetime.now(timezone)
        next_run = _next_weekly_standings_refresh(now)
        delay_seconds = max((next_run - now).total_seconds(), 1.0)
        logger.info(
            "Next automatic standings refresh scheduled for %s",
            next_run.isoformat(),
        )
        await asyncio.sleep(delay_seconds)

        try:
            from app.api.v1.league import refresh_standings_from_remote

            with database_manager.get_session() as db:
                fetched, count = refresh_standings_from_remote(db)
            logger.info(
                "Automatic standings refresh imported %d rows from %s (%s)",
                count,
                fetched.source_url,
                fetched.source_kind,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Automatic standings refresh failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager for startup and shutdown events.
    """
    # Startup
    logger.info(f"Starting {settings.project_name}...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")

    auto_refresh_task: asyncio.Task[None] | None = None

    try:
        # Initialize database
        init_db()
        logger.info("Database initialized successfully")

        # Test database connection
        try:
            health_check_passed = database_manager.health_check()
            if health_check_passed:
                logger.info("Database health check passed")
            else:
                logger.warning("Database health check failed but continuing startup")
        except Exception as e:
            logger.warning(f"Database health check failed but continuing startup: {e}")

        if settings.fantacalcio_auto_standings_enabled:
            auto_refresh_task = asyncio.create_task(
                _weekly_standings_refresh_loop(),
                name="weekly-standings-refresh",
            )
            logger.info("Automatic weekly standings refresh enabled")

        logger.info(f"{settings.project_name} startup complete")
        yield

    except Exception as e:
        logger.error(f"Startup error: {e}")
        if settings.is_development:
            logger.warning("Continuing startup in development mode despite errors")
            yield
        else:
            raise

    # Shutdown
    logger.info(f"Shutting down {settings.project_name}...")

    try:
        if auto_refresh_task is not None:
            auto_refresh_task.cancel()
            with suppress(asyncio.CancelledError):
                await auto_refresh_task
        close_db()
        logger.info("Application shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


def create_application() -> FastAPI:
    """Create and configure the FastAPI application"""

    # Create FastAPI application with correct OpenAPI configuration
    app = FastAPI(
        title=settings.project_name,
        version=settings.version,
        description="Modern API",
        docs_url=None,  # Disable default docs - we'll set up custom ones
        redoc_url=None,  # Disable default redoc - we'll set up custom ones
        openapi_url=(
            "/openapi.json" if (settings.debug or settings.is_staging) else None
        ),  # Keep OpenAPI JSON accessible
        debug=settings.debug,
        lifespan=lifespan,
    )

    # Setup exception handlers
    setup_exception_handlers(app)

    # Add middleware stack (order matters - reverse order of execution)

    # 1. CORS middleware (outermost)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Accept",
            "Origin",
            "User-Agent",
            "X-Requested-With",
            "X-Client-Info",
            "X-Dev-User",
            "X-Admin-Token",
        ],
        expose_headers=["X-Total-Count", "X-Rate-Limit-Remaining"],
        max_age=3600,  # Cache preflight requests for 1 hour
    )

    # 2. Rate limiting middleware (enabled in production and staging)
    if settings.is_production_like:
        app.add_middleware(
            RateLimitingMiddleware,
            requests=settings.rate_limit_requests,
            window=settings.rate_limit_window,
        )

    # 3. Security headers middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # 4. Request logging middleware (innermost)
    if settings.debug or settings.log_level.upper() in ["DEBUG", "INFO"]:
        app.add_middleware(LoggingMiddleware)

    # Add API routes
    app.include_router(api_router, prefix=settings.api_v1_str)

    # Add health check endpoints
    setup_health_endpoints(app)

    # Setup documentation endpoints based on environment
    setup_documentation_endpoints(app)

    return app


def setup_health_endpoints(app: FastAPI) -> None:
    """Setup health check and monitoring endpoints"""

    @app.get("/")
    async def read_root() -> Dict[str, Any]:
        """Root endpoint with API information"""
        return {
            "message": f"Welcome to the {settings.project_name}!",
            "version": settings.version,
            "status": "operational",
            "environment": settings.environment,
            "api_version": "v1",
            "docs_url": "/docs" if settings.debug else None,
            "redoc_url": "/redoc" if settings.debug else None,
        }

    @app.get("/health")
    async def health_check() -> Dict[str, str]:
        """Simple health check endpoint - just return OK"""
        return {"status": "ok"}


def setup_documentation_endpoints(app: FastAPI) -> None:
    """Setup documentation endpoints - always accessible in local development"""

    logger.info("Setting up open documentation endpoints for local development")

    @app.get("/docs", include_in_schema=False)
    def swagger_ui():
        """Swagger UI - open access for local development"""
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title=f"{app.title} – API Documentation",
            swagger_js_url="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-bundle.js",
            swagger_css_url="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui.css",
        )

    @app.get("/redoc", include_in_schema=False)
    def redoc_ui():
        """ReDoc UI - open access for local development"""
        return get_redoc_html(
            openapi_url="/openapi.json",
            title=f"{app.title} – API Documentation",
            redoc_js_url="https://unpkg.com/redoc@2.1.0/bundles/redoc.standalone.js",
        )

    @app.get("/openapi.json", include_in_schema=False)
    def get_openapi_json():
        """OpenAPI JSON schema"""
        return get_openapi(title=app.title, version=app.version, routes=app.routes)


# Create the application instance
app = create_application()

# For development server compatibility
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
