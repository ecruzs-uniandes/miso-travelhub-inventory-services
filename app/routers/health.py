import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.services import kafka_producer as kp

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health")
async def health(db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    db_status = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"DB health check failed: {e}")
        db_status = "error"

    kafka_status = "disabled"
    if settings.kafka_enabled:
        kafka_status = "ok" if kp.get_producer() is not None else "error"

    overall = "ok" if db_status == "ok" else "degraded"
    return {"status": overall, "service": settings.service_name, "database": db_status, "kafka": kafka_status}
