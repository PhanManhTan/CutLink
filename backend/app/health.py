import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import health_engine

router = APIRouter(prefix="/api/health", tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/live")
def live():
    return {"status": "alive"}


@router.get("/ready")
def ready():
    try:
        with health_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.warning("Database readiness failed", exc_info=True)
        return JSONResponse({"status": "unavailable"}, status_code=503)
    return {"status": "ready"}
