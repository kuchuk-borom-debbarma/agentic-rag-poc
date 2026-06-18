"""Application factory with lifespan-managed container.

Container is built once at startup and stored on app.state.container.
All route handlers access services through FastAPI Depends.
"""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from assessment_app.config.container import build_container
from assessment_app.config.exception_handlers import register_exception_handlers
from assessment_app.config.settings import load_settings
from assessment_app.routes.api_router import api_router

# Configure root logger to output INFO level logs
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-9s %(message)s"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build and store the DI container at startup; clean up at shutdown."""
    settings = load_settings()
    app.state.container = build_container(settings)
    yield
    # Add explicit close/cleanup of long-lived clients here if needed.


def create_app() -> FastAPI:
    settings = load_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()
