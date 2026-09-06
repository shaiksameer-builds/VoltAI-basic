"""
VoltAI Backend — Application Entry Point

This is the FastAPI application factory. It creates and configures
the main application instance.

Currently provides only a health-check endpoint.
Additional routers, middleware, and startup events will be
registered here as the application grows.
"""

from fastapi import FastAPI


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        FastAPI: The configured application instance.
    """
    application = FastAPI(
        title="VoltAI API",
        description="AI-Powered Renewable Energy Intelligence & Optimization",
        version="0.1.0",
    )

    # ---- Health Check ----
    @application.get("/health", tags=["System"])
    async def health_check():
        """
        Basic health-check endpoint.
        Returns the application status and version.
        """
        return {
            "status": "healthy",
            "version": application.version,
        }

    return application


# Application instance used by uvicorn
app = create_app()
