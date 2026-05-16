import logging
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.audit.listeners import register_tarifa_audit_listeners
from app.config import settings
from app.routers import health, tarifas
from app.services import kafka_producer as kp

logging.basicConfig(level=settings.log_level)
structlog.configure()


@asynccontextmanager
async def lifespan(app: FastAPI):
    kp.get_producer()  # initialize on startup if kafka_enabled
    register_tarifa_audit_listeners()
    yield
    kp.close_producer()


app = FastAPI(title="inventory-services", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(tarifas.router)


@app.get("/")
async def root() -> dict:
    return {"service": settings.service_name, "version": "0.1.0"}
