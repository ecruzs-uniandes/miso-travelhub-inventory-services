import logging
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.audit.listeners import register_rate_audit_listeners
from app.config import settings
from app.routers import health, rates
from app.services import kafka_producer as kp

logging.basicConfig(level=settings.log_level)
structlog.configure()


@asynccontextmanager
async def lifespan(app: FastAPI):
    kp.get_producer()  # initialize on startup if kafka_enabled
    register_rate_audit_listeners()
    yield
    kp.close_producer()


app = FastAPI(title="inventory-services", version="0.1.0", lifespan=lifespan)

app.include_router(health.router)
app.include_router(rates.router)


@app.get("/")
async def root() -> dict:
    return {"service": settings.service_name, "version": "0.1.0"}
