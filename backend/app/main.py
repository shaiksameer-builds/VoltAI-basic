"""
VoltAI Backend — Application Entry Point

This is the FastAPI application factory. It creates and configures
the main application instance.

Endpoints:
    GET /        — Application identity and status.
    GET /health  — Health check for monitoring.

Additional routers, middleware, and startup events will be
registered here as the application grows.
"""

from fastapi import FastAPI

from backend.app.api.v1.analytics import router as analytics_router
from backend.app.api.v1.anomalies import router as anomalies_router
from backend.app.api.v1.energy import router as energy_router
from backend.app.api.v1.forecast import router as forecast_router
from backend.app.api.v1.optimization import router as optimization_router


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        FastAPI: The configured application instance.
    """
    application = FastAPI(
        title="VoltAI API",
        description=(
            "AI-Powered Renewable Energy Intelligence & Optimization. "
            "Built for Smart India Hackathon 2026 — Problem Statement SIH26200."
        ),
        version="0.1.0",
    )

    # ---- Routers ----
    application.include_router(energy_router)
    application.include_router(analytics_router)
    application.include_router(forecast_router)
    application.include_router(optimization_router)
    application.include_router(anomalies_router)




    # ---- Root ----
    @application.get("/", tags=["System"])
    async def root():
        """
        Root endpoint.
        Returns application identity and confirms the backend is running.
        """
        return {
            "application": "VoltAI",
            "description": "AI-Powered Renewable Energy Intelligence & Optimization",
            "version": application.version,
            "status": "running",
        }

    # ---- Health Check ----
    @application.get("/health", tags=["System"])
    async def health_check():
        """
        Health-check endpoint for monitoring.
        Returns the current health status of the backend service.
        """
        return {
            "status": "healthy",
            "service": "voltai-backend",
            "version": application.version,
        }

    return application


# Application instance used by uvicorn
app = create_app()
