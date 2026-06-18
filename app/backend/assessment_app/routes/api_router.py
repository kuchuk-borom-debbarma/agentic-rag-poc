"""Central API router.

Aggregates all bounded-context sub-routers under a single include point in main.py.
"""

from fastapi import APIRouter

from assessment_app.routes.analytics_routes import router as analytics_router
from assessment_app.routes.ask_routes import router as ask_router
from assessment_app.routes.evaluation_routes import router as evaluation_router
from assessment_app.routes.health_routes import router as health_router
from assessment_app.routes.ingest_routes import router as ingest_router

api_router = APIRouter()

api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(ingest_router, prefix="/ingest", tags=["ingest"])
api_router.include_router(ask_router, prefix="/ask", tags=["ask"])
api_router.include_router(analytics_router, prefix="/analytics", tags=["analytics"])
api_router.include_router(evaluation_router, prefix="/evaluation", tags=["evaluation"])
