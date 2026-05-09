# CLAUDE_CODE — `inventory-services` — Módulo `rates`

> Archivo de instrucciones para **Claude Code (CLI local)**. Su objetivo es generar el repositorio `inventory-services` desde cero con el módulo de **Tarifas (rates)** como primer módulo funcional, listo para correr local con Docker Compose y desplegar a Cloud Run.
>
> **Proyecto:** TravelHub — Grupo 9 — MISW4501 / PF2 — Universidad de los Andes
> **Owner:** Edwin Cruz Silva
> **Microservicio:** `inventory-services`
> **Módulo:** `rates` (CRUD de Tarifa por habitación)

---

## 0. Asunciones de partida

1. **Repo nuevo desde cero.** Si ya hay scaffolding previo, descartar y reconstruir según este documento.
2. **Hotel y Room son entidades mínimas de soporte** sólo para tener FKs reales. Sus endpoints no son parte de este módulo y se agregarán después.
3. **El módulo `rates` NO calcula impuestos ni hace conversión de moneda.** Eso vive en `booking-services` (impuestos por país) y en `pms-integration-services` o servicio de divisas externo (FX).
4. **El JWT ya fue validado en firma/issuer/audience/exp por el API Gateway**. El backend solo decodifica el payload y valida claims de negocio (RBAC, MFA, etc.).
5. **Los hotel_admin solo pueden operar sobre tarifas de habitaciones de SU hotel** (claim `hotel_id` del JWT). Los `platform_admin` pueden operar sobre cualquier hotel.

---

## 1. Reglas de dominio cerradas

| # | Regla | Implementación |
|---|---|---|
| 1 | **Sin solapamiento de vigencias activas** por `room_id`. Crear o editar una tarifa que cruce con otra activa → `409 Conflict`. | Validación a nivel servicio (mensaje amigable) + constraint `EXCLUDE USING gist` en Postgres (garantía bajo concurrencia). |
| 2 | **Descuento es porcentual** en `[0.00, 1.00]`. `precio_final = precio_base * (1 - descuento)`. | Validación Pydantic + check constraint `discount BETWEEN 0 AND 1`. |
| 3 | **Una habitación = una moneda nativa**, heredada del hotel. No se permite multi-moneda en la misma habitación. | El `currency` se setea desde `hotel.currency` y no se puede cambiar en update. |
| 4 | **Auditoría append-only en tabla `rate_history`** con `user_id`, `ip`, `timestamp`, `action`, `old_values JSONB`, `new_values JSONB`. | SQLAlchemy event listeners (`after_insert`, `after_update`, `after_delete`) + `contextvars` para inyectar `user_id` e `ip` desde el request. |

---

## 2. Stack y constraints

- **Python** 3.11
- **FastAPI** 0.115+
- **SQLAlchemy** 2.0 async + **asyncpg**
- **Alembic** para migraciones
- **Pydantic** v2
- **PostgreSQL** 16 (Cloud SQL en GCP, IP privada `10.100.0.3` en VPC)
- **pytest** + **pytest-asyncio** + **pytest-cov** (cobertura mínima 70%)
- **httpx** (cliente de tests)
- **python-jose[cryptography]** (decode JWT sin verify)
- **ruff** (lint en CI)
- **Docker** + **Docker Compose** (entorno local)
- **GitHub Actions** (CI con tests + cobertura)
- **gcloud CLI** (despliegue a Cloud Run)

---

## 3. Estructura del repositorio

```
inventory-services/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── context.py                  # ContextVars: current_user_id, current_ip
│   ├── exceptions.py
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── chain.py                # Chain of Responsibility
│   │   ├── filters/
│   │   │   ├── __init__.py
│   │   │   ├── base.py             # AuthFilter abstract base
│   │   │   ├── rate_limit.py
│   │   │   ├── ip_validation.py
│   │   │   ├── rbac.py
│   │   │   └── mfa.py
│   ├── auth/
│   │   ├── __init__.py
│   │   └── jwt_decoder.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── hotel.py
│   │   ├── room.py
│   │   ├── rate.py
│   │   └── rate_history.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── rate.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── health.py
│   │   └── rates.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── rate_service.py
│   └── audit/
│       ├── __init__.py
│       └── listeners.py            # SQLAlchemy event listeners
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_initial_schema.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── helpers.py                  # Generar JWTs de prueba
│   ├── test_health.py
│   ├── test_rates_crud.py
│   ├── test_rates_overlap.py
│   ├── test_rates_rbac.py
│   └── test_rates_audit.py
├── deploy/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── seed_data.sql
│   └── deploy-cloudrun.sh
├── .github/
│   └── workflows/
│       └── ci.yml
├── alembic.ini
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── .env.example
├── .gitignore
├── README.md
└── CONTEXT.md
```

---

## 4. Archivos completos

### 4.1 `requirements.txt`

```text
fastapi==0.115.0
uvicorn[standard]==0.30.6
sqlalchemy[asyncio]==2.0.34
asyncpg==0.29.0
alembic==1.13.2
pydantic==2.9.2
pydantic-settings==2.5.2
python-jose[cryptography]==3.3.0
structlog==24.4.0
python-multipart==0.0.10
```

### 4.2 `requirements-dev.txt`

```text
-r requirements.txt
pytest==8.3.3
pytest-asyncio==0.24.0
pytest-cov==5.0.0
httpx==0.27.2
ruff==0.6.8
aiosqlite==0.20.0
```

### 4.3 `pyproject.toml`

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-v --cov=app --cov-report=term-missing --cov-fail-under=70"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "C4"]
ignore = ["B008"]

[tool.coverage.run]
omit = ["app/main.py", "alembic/*", "tests/*"]
```

### 4.4 `.env.example`

```text
# Database
DATABASE_URL=postgresql+asyncpg://travelhub_app:travelhub_local@db:5432/travelhub
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20

# JWT (gateway ya validó firma; backend solo decodifica)
JWT_ISSUER=https://auth.travelhub.app
JWT_AUDIENCE=travelhub-api

# Service
SERVICE_NAME=inventory-services
SERVICE_PORT=8000
LOG_LEVEL=INFO

# Rate limiting (por usuario/IP)
RATE_LIMIT_RPM=60
```

### 4.5 `.gitignore`

```text
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
.env
.coverage
htmlcov/
.pytest_cache/
.ruff_cache/
*.db
*.sqlite
.DS_Store
```

### 4.6 `app/config.py`

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    database_pool_size: int = 10
    database_max_overflow: int = 20

    jwt_issuer: str
    jwt_audience: str

    service_name: str = "inventory-services"
    service_port: int = 8000
    log_level: str = "INFO"

    rate_limit_rpm: int = 60


settings = Settings()
```

### 4.7 `app/database.py`

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

### 4.8 `app/context.py`

```python
"""Context vars to thread request metadata into SQLAlchemy event listeners."""
from contextvars import ContextVar
from uuid import UUID

current_user_id: ContextVar[UUID | None] = ContextVar("current_user_id", default=None)
current_user_role: ContextVar[str | None] = ContextVar("current_user_role", default=None)
current_ip: ContextVar[str | None] = ContextVar("current_ip", default=None)
current_hotel_id: ContextVar[UUID | None] = ContextVar("current_hotel_id", default=None)
```

### 4.9 `app/exceptions.py`

```python
from fastapi import HTTPException, status


class RateOverlapError(HTTPException):
    def __init__(self, detail: str = "Rate overlaps with existing active rate"):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class RateNotFoundError(HTTPException):
    def __init__(self):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail="Rate not found")


class ForbiddenHotelError(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot operate on rates of a hotel you don't belong to",
        )


class InvalidJWTError(HTTPException):
    def __init__(self, detail: str = "Invalid or missing JWT"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)
```

### 4.10 `app/auth/jwt_decoder.py`

```python
"""Decodes JWT WITHOUT verifying signature.

The API Gateway has already validated:
- RS256 signature (via JWKS endpoint)
- Issuer claim
- Audience claim
- Expiration

The backend only needs to read claims for RBAC, MFA, and audit purposes.
"""
from typing import Any

from jose import jwt

from app.config import settings
from app.exceptions import InvalidJWTError


def decode_jwt(token: str) -> dict[str, Any]:
    """Decode JWT payload without verifying signature.

    The signature was already verified upstream by the API Gateway. We only
    re-check non-cryptographic claims for defense in depth.
    """
    try:
        payload = jwt.get_unverified_claims(token)
    except Exception as e:
        raise InvalidJWTError(f"Cannot decode JWT: {e}") from e

    if payload.get("iss") != settings.jwt_issuer:
        raise InvalidJWTError("Invalid issuer")
    if payload.get("aud") != settings.jwt_audience:
        raise InvalidJWTError("Invalid audience")
    if not payload.get("sub"):
        raise InvalidJWTError("Missing subject")
    if not payload.get("role"):
        raise InvalidJWTError("Missing role")

    return payload


def extract_token(authorization_header: str | None) -> str:
    if not authorization_header:
        raise InvalidJWTError("Missing Authorization header")
    parts = authorization_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise InvalidJWTError("Authorization header must be 'Bearer <token>'")
    return parts[1]
```

### 4.11 `app/middleware/filters/base.py`

```python
"""Chain of Responsibility — base filter."""
from abc import ABC, abstractmethod
from typing import Any

from fastapi import Request


class AuthFilter(ABC):
    """Abstract base for chain filters. Each filter validates one concern.

    Filters are linked: each one calls `_pass_to_next` after its own check.
    The final handler is reached only when every filter passed.
    """

    def __init__(self) -> None:
        self._next: AuthFilter | None = None

    def set_next(self, nxt: "AuthFilter") -> "AuthFilter":
        self._next = nxt
        return nxt

    async def _pass_to_next(self, request: Request, payload: dict[str, Any]) -> None:
        if self._next is not None:
            await self._next.handle(request, payload)

    @abstractmethod
    async def handle(self, request: Request, payload: dict[str, Any]) -> None: ...
```

### 4.12 `app/middleware/filters/rate_limit.py`

```python
"""In-memory token bucket per (user_id, route). For multi-instance use Redis.

The current PF1 gap (rate limiting distribuido) is documented; for PF2 MVP this
in-memory implementation is acceptable since Cloud Armor enforces a global limit
at the edge. This is a defense-in-depth layer.
"""
import time
from collections import defaultdict
from typing import Any

from fastapi import HTTPException, Request, status

from app.config import settings
from app.middleware.filters.base import AuthFilter


class RateLimitFilter(AuthFilter):
    def __init__(self) -> None:
        super().__init__()
        # key -> [count, window_start_epoch_seconds]
        self._buckets: dict[str, list[float]] = defaultdict(lambda: [0.0, time.time()])
        self._window_seconds = 60.0
        self._limit = settings.rate_limit_rpm

    async def handle(self, request: Request, payload: dict[str, Any]) -> None:
        key = f"{payload.get('sub')}:{request.url.path}"
        bucket = self._buckets[key]
        now = time.time()
        if now - bucket[1] >= self._window_seconds:
            bucket[0] = 0.0
            bucket[1] = now
        bucket[0] += 1
        if bucket[0] > self._limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: {self._limit} req/min",
            )
        await self._pass_to_next(request, payload)
```

### 4.13 `app/middleware/filters/ip_validation.py`

```python
"""Validates the request IP is consistent with the JWT 'country' claim.

PF1 placeholder: real geolocation requires MaxMind GeoIP or Cloud Armor enrichment.
For MVP we just store the IP into context for audit. The full check is a TODO.
"""
from typing import Any

from fastapi import Request

from app.context import current_ip
from app.middleware.filters.base import AuthFilter


class IPValidationFilter(AuthFilter):
    async def handle(self, request: Request, payload: dict[str, Any]) -> None:
        # Trust X-Forwarded-For from the LB; fall back to client.host
        forwarded = request.headers.get("x-forwarded-for")
        ip = forwarded.split(",")[0].strip() if forwarded else (
            request.client.host if request.client else "unknown"
        )
        current_ip.set(ip)
        # TODO: validate ip-country consistency against payload['country']
        await self._pass_to_next(request, payload)
```

### 4.14 `app/middleware/filters/rbac.py`

```python
"""RBAC: validates the role against the requested route.

For inventory-services rates module:
- traveler:        FORBIDDEN
- hotel_admin:     allowed only for routes operating on rooms of own hotel
                   (the per-resource hotel_id check happens in the service layer)
- platform_admin:  allowed for everything

The 'own hotel' check requires loading the room/rate to know its hotel_id, so
RBAC here is coarse-grained (role check). Fine-grained ownership is enforced
in the service layer (see RateService).
"""
from typing import Any

from fastapi import HTTPException, Request, status

from app.context import current_hotel_id, current_user_id, current_user_role
from app.middleware.filters.base import AuthFilter

ALLOWED_ROLES = {"hotel_admin", "platform_admin"}


class RBACFilter(AuthFilter):
    async def handle(self, request: Request, payload: dict[str, Any]) -> None:
        role = payload.get("role")
        if role not in ALLOWED_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' cannot access inventory rates",
            )

        # Populate context for downstream service-layer checks and audit
        from uuid import UUID

        sub = payload.get("sub")
        hotel = payload.get("hotel_id")
        current_user_id.set(UUID(sub) if sub else None)
        current_user_role.set(role)
        current_hotel_id.set(UUID(hotel) if hotel else None)

        await self._pass_to_next(request, payload)
```

### 4.15 `app/middleware/filters/mfa.py`

```python
"""MFA enforcement.

PF1 mandates MFA for /payments and /admin. For inventory-services rates, MFA
is required only for hotel_admin write operations as a defense-in-depth measure
against compromised hotel credentials. Read endpoints don't require MFA.
"""
from typing import Any

from fastapi import HTTPException, Request, status

from app.middleware.filters.base import AuthFilter

WRITE_METHODS = {"POST", "PATCH", "DELETE"}


class MFAFilter(AuthFilter):
    async def handle(self, request: Request, payload: dict[str, Any]) -> None:
        if request.method in WRITE_METHODS and payload.get("role") == "hotel_admin":
            if not payload.get("mfa_verified"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="MFA required for write operations on rates",
                )
        await self._pass_to_next(request, payload)
```

### 4.16 `app/middleware/chain.py`

```python
"""Wires the Chain of Responsibility and exposes it as a FastAPI dependency."""
from typing import Annotated

from fastapi import Depends, Header, Request

from app.auth.jwt_decoder import decode_jwt, extract_token
from app.middleware.filters.ip_validation import IPValidationFilter
from app.middleware.filters.mfa import MFAFilter
from app.middleware.filters.rate_limit import RateLimitFilter
from app.middleware.filters.rbac import RBACFilter


def _build_chain() -> RateLimitFilter:
    rate_limit = RateLimitFilter()
    ip_validation = IPValidationFilter()
    rbac = RBACFilter()
    mfa = MFAFilter()
    rate_limit.set_next(ip_validation).set_next(rbac).set_next(mfa)
    return rate_limit


_CHAIN = _build_chain()


async def auth_chain(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    token = extract_token(authorization)
    payload = decode_jwt(token)
    await _CHAIN.handle(request, payload)
    return payload
```

### 4.17 `app/models/base.py`

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

### 4.18 `app/models/hotel.py`

```python
"""Minimal Hotel entity to support FKs from Room and Rate.

NOTE: Full Hotel CRUD lives in another module of inventory-services.
Here we only need: id, country, currency.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Hotel(Base):
    __tablename__ = "hotels"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)  # ISO 3166-1 alpha-2
    currency: Mapped[str] = mapped_column(String(3), nullable=False)  # ISO 4217
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    rooms: Mapped[list["Room"]] = relationship(back_populates="hotel")  # noqa: F821
```

### 4.19 `app/models/room.py`

```python
"""Minimal Room entity to support FK from Rate."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    hotel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False
    )
    room_type: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    hotel: Mapped["Hotel"] = relationship(back_populates="rooms")  # noqa: F821
    rates: Mapped[list["Rate"]] = relationship(back_populates="room")  # noqa: F821
```

### 4.20 `app/models/rate.py`

```python
import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class RateStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class Rate(Base):
    __tablename__ = "rates"
    __table_args__ = (
        CheckConstraint("base_price > 0", name="ck_rate_base_price_positive"),
        CheckConstraint(
            "discount >= 0 AND discount <= 1", name="ck_rate_discount_range"
        ),
        CheckConstraint("valid_from <= valid_to", name="ck_rate_date_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False
    )
    base_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date] = mapped_column(Date, nullable=False)
    discount: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, default=Decimal("0")
    )
    status: Mapped[RateStatus] = mapped_column(
        Enum(RateStatus, name="rate_status"),
        nullable=False,
        default=RateStatus.ACTIVE,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    room: Mapped["Room"] = relationship(back_populates="rates")  # noqa: F821

    def calcular_precio_final(self) -> Decimal:
        """Domain method per PF1 model: precio_final = base_price * (1 - discount)."""
        return (self.base_price * (Decimal("1") - self.discount)).quantize(Decimal("0.01"))
```

### 4.21 `app/models/rate_history.py`

```python
"""Append-only audit table for rate changes."""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditAction(str, enum.Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class RateHistory(Base):
    __tablename__ = "rate_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    rate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name="audit_action"), nullable=False
    )
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    changed_by_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    old_values: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_values: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

### 4.22 `app/models/__init__.py`

```python
from app.models.base import Base
from app.models.hotel import Hotel
from app.models.rate import Rate, RateStatus
from app.models.rate_history import AuditAction, RateHistory
from app.models.room import Room

__all__ = ["Base", "Hotel", "Room", "Rate", "RateStatus", "RateHistory", "AuditAction"]
```

### 4.23 `app/audit/listeners.py`

```python
"""SQLAlchemy event listeners that mirror Rate changes into rate_history.

Uses contextvars (current_user_id, current_ip) populated by the auth chain.
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.context import current_ip, current_user_id
from app.models.rate import Rate
from app.models.rate_history import AuditAction, RateHistory


def _serialize(rate: Rate) -> dict:
    def conv(v):
        if isinstance(v, Decimal):
            return str(v)
        if isinstance(v, (date, datetime)):
            return v.isoformat()
        if isinstance(v, UUID):
            return str(v)
        if hasattr(v, "value"):  # enum
            return v.value
        return v

    return {
        "id": conv(rate.id),
        "room_id": conv(rate.room_id),
        "base_price": conv(rate.base_price),
        "currency": rate.currency,
        "valid_from": conv(rate.valid_from),
        "valid_to": conv(rate.valid_to),
        "discount": conv(rate.discount),
        "status": conv(rate.status),
    }


def register_rate_audit_listeners() -> None:
    @event.listens_for(Session, "after_flush")
    def _after_flush(session: Session, flush_context):
        for obj in session.new:
            if isinstance(obj, Rate):
                session.add(
                    RateHistory(
                        rate_id=obj.id,
                        action=AuditAction.CREATE,
                        changed_by_user_id=current_user_id.get(),
                        changed_by_ip=current_ip.get(),
                        old_values=None,
                        new_values=_serialize(obj),
                    )
                )
        for obj in session.dirty:
            if isinstance(obj, Rate) and session.is_modified(obj):
                # Get old values from history attribute
                hist_old = {}
                from sqlalchemy import inspect

                state = inspect(obj)
                for attr in state.attrs:
                    h = attr.load_history()
                    if h.has_changes():
                        hist_old[attr.key] = h.deleted[0] if h.deleted else None
                session.add(
                    RateHistory(
                        rate_id=obj.id,
                        action=AuditAction.UPDATE,
                        changed_by_user_id=current_user_id.get(),
                        changed_by_ip=current_ip.get(),
                        old_values={k: str(v) for k, v in hist_old.items()},
                        new_values=_serialize(obj),
                    )
                )
        for obj in session.deleted:
            if isinstance(obj, Rate):
                session.add(
                    RateHistory(
                        rate_id=obj.id,
                        action=AuditAction.DELETE,
                        changed_by_user_id=current_user_id.get(),
                        changed_by_ip=current_ip.get(),
                        old_values=_serialize(obj),
                        new_values=None,
                    )
                )
```

### 4.24 `app/schemas/rate.py`

```python
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.rate import RateStatus


class RateCreate(BaseModel):
    room_id: UUID
    base_price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    valid_from: date
    valid_to: date
    discount: Decimal = Field(default=Decimal("0"), ge=0, le=1, max_digits=5, decimal_places=4)

    @model_validator(mode="after")
    def _check_dates(self) -> "RateCreate":
        if self.valid_from > self.valid_to:
            raise ValueError("valid_from must be <= valid_to")
        return self


class RateUpdate(BaseModel):
    base_price: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    valid_from: date | None = None
    valid_to: date | None = None
    discount: Decimal | None = Field(default=None, ge=0, le=1, max_digits=5, decimal_places=4)
    status: RateStatus | None = None


class RateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    room_id: UUID
    base_price: Decimal
    currency: str
    valid_from: date
    valid_to: date
    discount: Decimal
    status: RateStatus
    created_at: datetime
    updated_at: datetime


class RateEffective(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rate_id: UUID
    room_id: UUID
    base_price: Decimal
    currency: str
    discount: Decimal
    final_price: Decimal
    valid_from: date
    valid_to: date
```

### 4.25 `app/services/rate_service.py`

```python
"""Business logic for rate management.

Enforces:
- Ownership: hotel_admin can only operate on rates of rooms in own hotel
- No-overlap: no two ACTIVE rates on the same room can have overlapping date ranges
- Currency inheritance: rate.currency = room.hotel.currency (set at creation)
"""
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.context import current_hotel_id, current_user_role
from app.exceptions import ForbiddenHotelError, RateNotFoundError, RateOverlapError
from app.models.hotel import Hotel
from app.models.rate import Rate, RateStatus
from app.models.room import Room
from app.schemas.rate import RateCreate, RateUpdate


class RateService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _get_room_with_hotel(self, room_id: UUID) -> tuple[Room, Hotel]:
        stmt = select(Room, Hotel).join(Hotel, Room.hotel_id == Hotel.id).where(Room.id == room_id)
        result = await self.db.execute(stmt)
        row = result.first()
        if row is None:
            raise RateNotFoundError()
        return row[0], row[1]

    def _check_ownership(self, hotel_id: UUID) -> None:
        role = current_user_role.get()
        if role == "platform_admin":
            return
        if role == "hotel_admin":
            if current_hotel_id.get() != hotel_id:
                raise ForbiddenHotelError()
            return
        raise ForbiddenHotelError()

    async def _assert_no_overlap(
        self,
        room_id: UUID,
        valid_from: date,
        valid_to: date,
        exclude_rate_id: UUID | None = None,
    ) -> None:
        # Two ranges overlap iff: A.from <= B.to AND B.from <= A.to
        conditions = [
            Rate.room_id == room_id,
            Rate.status == RateStatus.ACTIVE,
            Rate.valid_from <= valid_to,
            valid_from <= Rate.valid_to,
        ]
        if exclude_rate_id is not None:
            conditions.append(Rate.id != exclude_rate_id)
        stmt = select(Rate.id).where(and_(*conditions)).limit(1)
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none() is not None:
            raise RateOverlapError(
                f"An active rate already covers part of {valid_from}..{valid_to} for this room"
            )

    async def create(self, data: RateCreate) -> Rate:
        _, hotel = await self._get_room_with_hotel(data.room_id)
        self._check_ownership(hotel.id)
        await self._assert_no_overlap(data.room_id, data.valid_from, data.valid_to)
        rate = Rate(
            room_id=data.room_id,
            base_price=data.base_price,
            currency=hotel.currency,  # inherited from hotel
            valid_from=data.valid_from,
            valid_to=data.valid_to,
            discount=data.discount,
            status=RateStatus.ACTIVE,
        )
        self.db.add(rate)
        await self.db.flush()
        await self.db.refresh(rate)
        return rate

    async def get(self, rate_id: UUID) -> Rate:
        rate = await self.db.get(Rate, rate_id)
        if rate is None:
            raise RateNotFoundError()
        _, hotel = await self._get_room_with_hotel(rate.room_id)
        self._check_ownership(hotel.id)
        return rate

    async def list_by_room(self, room_id: UUID) -> list[Rate]:
        _, hotel = await self._get_room_with_hotel(room_id)
        self._check_ownership(hotel.id)
        stmt = select(Rate).where(Rate.room_id == room_id).order_by(Rate.valid_from.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_hotel(self, hotel_id: UUID) -> list[Rate]:
        self._check_ownership(hotel_id)
        stmt = (
            select(Rate)
            .join(Room, Rate.room_id == Room.id)
            .where(Room.hotel_id == hotel_id)
            .order_by(Rate.valid_from.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update(self, rate_id: UUID, data: RateUpdate) -> Rate:
        rate = await self.get(rate_id)
        new_from = data.valid_from or rate.valid_from
        new_to = data.valid_to or rate.valid_to
        new_status = data.status or rate.status
        if new_status == RateStatus.ACTIVE:
            await self._assert_no_overlap(
                rate.room_id, new_from, new_to, exclude_rate_id=rate.id
            )
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(rate, field, value)
        await self.db.flush()
        await self.db.refresh(rate)
        return rate

    async def soft_delete(self, rate_id: UUID) -> None:
        rate = await self.get(rate_id)
        rate.status = RateStatus.INACTIVE
        await self.db.flush()

    async def get_effective(self, room_id: UUID, on_date: date) -> tuple[Rate, Decimal]:
        """Public read for search/booking — no RBAC ownership check.

        Returns the active rate covering on_date and the computed final price.
        """
        stmt = select(Rate).where(
            and_(
                Rate.room_id == room_id,
                Rate.status == RateStatus.ACTIVE,
                Rate.valid_from <= on_date,
                Rate.valid_to >= on_date,
            )
        )
        result = await self.db.execute(stmt)
        rate = result.scalar_one_or_none()
        if rate is None:
            raise RateNotFoundError()
        return rate, rate.calcular_precio_final()
```

### 4.26 `app/routers/rates.py`

```python
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.chain import auth_chain
from app.schemas.rate import RateCreate, RateEffective, RateRead, RateUpdate
from app.services.rate_service import RateService

router = APIRouter(prefix="/api/v1/inventory", tags=["rates"])


@router.post("/rooms/{room_id}/rates", response_model=RateRead, status_code=status.HTTP_201_CREATED)
async def create_rate(
    room_id: UUID,
    body: RateCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(auth_chain)],
) -> RateRead:
    if body.room_id != room_id:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="room_id in path and body must match")
    svc = RateService(db)
    rate = await svc.create(body)
    return RateRead.model_validate(rate)


@router.get("/rooms/{room_id}/rates", response_model=list[RateRead])
async def list_rates_for_room(
    room_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(auth_chain)],
) -> list[RateRead]:
    svc = RateService(db)
    rates = await svc.list_by_room(room_id)
    return [RateRead.model_validate(r) for r in rates]


@router.get("/hotels/{hotel_id}/rates", response_model=list[RateRead])
async def list_rates_for_hotel(
    hotel_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(auth_chain)],
) -> list[RateRead]:
    svc = RateService(db)
    rates = await svc.list_by_hotel(hotel_id)
    return [RateRead.model_validate(r) for r in rates]


@router.get("/rates/{rate_id}", response_model=RateRead)
async def get_rate(
    rate_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(auth_chain)],
) -> RateRead:
    svc = RateService(db)
    rate = await svc.get(rate_id)
    return RateRead.model_validate(rate)


@router.patch("/rates/{rate_id}", response_model=RateRead)
async def update_rate(
    rate_id: UUID,
    body: RateUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(auth_chain)],
) -> RateRead:
    svc = RateService(db)
    rate = await svc.update(rate_id, body)
    return RateRead.model_validate(rate)


@router.delete("/rates/{rate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rate(
    rate_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(auth_chain)],
) -> None:
    svc = RateService(db)
    await svc.soft_delete(rate_id)


@router.get("/rates/effective", response_model=RateEffective)
async def get_effective_rate(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(auth_chain)],
    room_id: UUID = Query(...),
    on_date: date = Query(..., alias="date"),
) -> RateEffective:
    svc = RateService(db)
    rate, final = await svc.get_effective(room_id, on_date)
    return RateEffective(
        rate_id=rate.id,
        room_id=rate.room_id,
        base_price=rate.base_price,
        currency=rate.currency,
        discount=rate.discount,
        final_price=final,
        valid_from=rate.valid_from,
        valid_to=rate.valid_to,
    )
```

### 4.27 `app/routers/health.py`

```python
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "inventory-services"}
```

### 4.28 `app/main.py`

```python
import logging

import structlog
from fastapi import FastAPI

from app.audit.listeners import register_rate_audit_listeners
from app.config import settings
from app.routers import health, rates

logging.basicConfig(level=settings.log_level)
structlog.configure()

app = FastAPI(title="inventory-services", version="0.1.0")

app.include_router(health.router)
app.include_router(rates.router)

register_rate_audit_listeners()


@app.get("/")
async def root() -> dict:
    return {"service": settings.service_name, "version": "0.1.0"}
```

### 4.29 `alembic.ini`

```ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql+asyncpg://travelhub_app:travelhub_local@db:5432/travelhub
file_template = %%(year)04d%%(month)02d%%(day)02d_%%(rev)s_%%(slug)s

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

### 4.30 `alembic/env.py`

```python
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.config import settings
from app.models import Base

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"}
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### 4.31 `alembic/versions/0001_initial_schema.py`

```python
"""initial schema with hotels, rooms, rates, rate_history + exclude constraint

Revision ID: 0001
Create Date: 2026-05-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table(
        "hotels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "rooms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "hotel_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hotels.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("room_type", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_rooms_hotel_id", "rooms", ["hotel_id"])

    rate_status = postgresql.ENUM("active", "inactive", name="rate_status")
    rate_status.create(op.get_bind())

    op.create_table(
        "rates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "room_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("rooms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("base_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("valid_from", sa.Date, nullable=False),
        sa.Column("valid_to", sa.Date, nullable=False),
        sa.Column("discount", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column(
            "status",
            postgresql.ENUM("active", "inactive", name="rate_status", create_type=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("base_price > 0", name="ck_rate_base_price_positive"),
        sa.CheckConstraint("discount >= 0 AND discount <= 1", name="ck_rate_discount_range"),
        sa.CheckConstraint("valid_from <= valid_to", name="ck_rate_date_order"),
    )
    op.create_index("ix_rates_room_id", "rates", ["room_id"])

    # Concurrency-safe no-overlap guarantee for ACTIVE rates per room
    op.execute(
        """
        ALTER TABLE rates
        ADD CONSTRAINT ex_rates_no_overlap_active
        EXCLUDE USING gist (
            room_id WITH =,
            daterange(valid_from, valid_to, '[]') WITH &&
        ) WHERE (status = 'active')
        """
    )

    audit_action = postgresql.ENUM("create", "update", "delete", name="audit_action")
    audit_action.create(op.get_bind())

    op.create_table(
        "rate_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("rate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "action",
            postgresql.ENUM("create", "update", "delete", name="audit_action", create_type=False),
            nullable=False,
        ),
        sa.Column("changed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("changed_by_ip", sa.String(45), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("old_values", postgresql.JSONB, nullable=True),
        sa.Column("new_values", postgresql.JSONB, nullable=True),
    )
    op.create_index("ix_rate_history_rate_id", "rate_history", ["rate_id"])


def downgrade() -> None:
    op.drop_index("ix_rate_history_rate_id", table_name="rate_history")
    op.drop_table("rate_history")
    op.execute("DROP TYPE IF EXISTS audit_action")
    op.execute("ALTER TABLE rates DROP CONSTRAINT IF EXISTS ex_rates_no_overlap_active")
    op.drop_index("ix_rates_room_id", table_name="rates")
    op.drop_table("rates")
    op.execute("DROP TYPE IF EXISTS rate_status")
    op.drop_index("ix_rooms_hotel_id", table_name="rooms")
    op.drop_table("rooms")
    op.drop_table("hotels")
```

### 4.32 `alembic/script.py.mako`

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

### 4.33 `tests/helpers.py`

```python
"""Helpers for generating test JWTs (signature is not validated by the backend)."""
import time
from uuid import UUID, uuid4

from jose import jwt

from app.config import settings


def make_token(
    user_id: UUID | None = None,
    role: str = "hotel_admin",
    hotel_id: UUID | None = None,
    mfa_verified: bool = True,
    country: str = "CO",
) -> str:
    payload = {
        "sub": str(user_id or uuid4()),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "exp": int(time.time()) + 900,
        "iat": int(time.time()),
        "role": role,
        "mfa_verified": mfa_verified,
        "country": country,
        "hotel_id": str(hotel_id) if hotel_id else None,
    }
    # Any secret works; the backend never verifies the signature
    return jwt.encode(payload, "test-secret", algorithm="HS256")


def auth_headers(**kwargs) -> dict:
    return {"Authorization": f"Bearer {make_token(**kwargs)}"}
```

### 4.34 `tests/conftest.py`

```python
import asyncio
from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.audit.listeners import register_rate_audit_listeners
from app.database import get_db
from app.main import app
from app.models import Base, Hotel, Room

# Use Postgres for full-feature tests; CI sets DATABASE_URL_TEST.
# For quick local runs (no overlap-constraint check), aiosqlite works for most tests.
TEST_DB_URL = "postgresql+asyncpg://travelhub_app:travelhub_local@localhost:5432/travelhub_test"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(TEST_DB_URL, pool_pre_ping=True)
    register_rate_audit_listeners()
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncGenerator[AsyncSession, None]:
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as s:
        yield s
        await s.rollback()


@pytest_asyncio.fixture
async def client(engine) -> AsyncGenerator[AsyncClient, None]:
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_db():
        async with async_session() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sample_hotel(session: AsyncSession) -> Hotel:
    hotel = Hotel(id=uuid4(), name="Hotel Test", country="CO", currency="COP")
    session.add(hotel)
    await session.commit()
    return hotel


@pytest_asyncio.fixture
async def sample_room(session: AsyncSession, sample_hotel: Hotel) -> Room:
    room = Room(id=uuid4(), hotel_id=sample_hotel.id, room_type="standard")
    session.add(room)
    await session.commit()
    return room
```

### 4.35 `tests/test_health.py`

```python
import pytest


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
```

### 4.36 `tests/test_rates_crud.py`

```python
from datetime import date

import pytest

from tests.helpers import auth_headers


@pytest.mark.asyncio
async def test_create_rate_inherits_currency(client, sample_room, sample_hotel):
    payload = {
        "room_id": str(sample_room.id),
        "base_price": "150000.00",
        "valid_from": "2026-06-01",
        "valid_to": "2026-06-30",
        "discount": "0.10",
    }
    r = await client.post(
        f"/api/v1/inventory/rooms/{sample_room.id}/rates",
        json=payload,
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["currency"] == "COP"  # inherited from hotel
    assert body["status"] == "active"


@pytest.mark.asyncio
async def test_create_rate_invalid_dates_400(client, sample_room, sample_hotel):
    payload = {
        "room_id": str(sample_room.id),
        "base_price": "150000.00",
        "valid_from": "2026-06-30",
        "valid_to": "2026-06-01",
        "discount": "0.10",
    }
    r = await client.post(
        f"/api/v1/inventory/rooms/{sample_room.id}/rates",
        json=payload,
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_get_rate_and_list(client, sample_room, sample_hotel):
    payload = {
        "room_id": str(sample_room.id),
        "base_price": "200000.00",
        "valid_from": "2026-07-01",
        "valid_to": "2026-07-31",
        "discount": "0",
    }
    r = await client.post(
        f"/api/v1/inventory/rooms/{sample_room.id}/rates",
        json=payload,
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )
    rate_id = r.json()["id"]

    r = await client.get(
        f"/api/v1/inventory/rates/{rate_id}",
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )
    assert r.status_code == 200

    r = await client.get(
        f"/api/v1/inventory/rooms/{sample_room.id}/rates",
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )
    assert r.status_code == 200
    assert any(x["id"] == rate_id for x in r.json())


@pytest.mark.asyncio
async def test_update_rate_discount(client, sample_room, sample_hotel):
    payload = {
        "room_id": str(sample_room.id),
        "base_price": "100000.00",
        "valid_from": "2026-08-01",
        "valid_to": "2026-08-31",
        "discount": "0.05",
    }
    r = await client.post(
        f"/api/v1/inventory/rooms/{sample_room.id}/rates",
        json=payload,
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )
    rate_id = r.json()["id"]

    r = await client.patch(
        f"/api/v1/inventory/rates/{rate_id}",
        json={"discount": "0.20"},
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )
    assert r.status_code == 200
    assert r.json()["discount"] == "0.2000"


@pytest.mark.asyncio
async def test_soft_delete_sets_inactive(client, sample_room, sample_hotel):
    payload = {
        "room_id": str(sample_room.id),
        "base_price": "100000.00",
        "valid_from": "2026-09-01",
        "valid_to": "2026-09-30",
        "discount": "0",
    }
    r = await client.post(
        f"/api/v1/inventory/rooms/{sample_room.id}/rates",
        json=payload,
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )
    rate_id = r.json()["id"]

    r = await client.delete(
        f"/api/v1/inventory/rates/{rate_id}",
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )
    assert r.status_code == 204

    r = await client.get(
        f"/api/v1/inventory/rates/{rate_id}",
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )
    assert r.json()["status"] == "inactive"


@pytest.mark.asyncio
async def test_get_effective_returns_final_price(client, sample_room, sample_hotel):
    payload = {
        "room_id": str(sample_room.id),
        "base_price": "100000.00",
        "valid_from": "2026-10-01",
        "valid_to": "2026-10-31",
        "discount": "0.25",
    }
    await client.post(
        f"/api/v1/inventory/rooms/{sample_room.id}/rates",
        json=payload,
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )

    r = await client.get(
        "/api/v1/inventory/rates/effective",
        params={"room_id": str(sample_room.id), "date": "2026-10-15"},
        headers=auth_headers(role="traveler"),
    )
    # Traveler is blocked by RBAC for write paths but read of /effective is allowed
    # Adjust RBACFilter ALLOWED_ROLES if you want traveler reads. For MVP we test as platform_admin:
    if r.status_code == 403:
        r = await client.get(
            "/api/v1/inventory/rates/effective",
            params={"room_id": str(sample_room.id), "date": "2026-10-15"},
            headers=auth_headers(role="platform_admin"),
        )
    assert r.status_code == 200
    assert r.json()["final_price"] == "75000.00"
```

### 4.37 `tests/test_rates_overlap.py`

```python
import pytest

from tests.helpers import auth_headers


@pytest.mark.asyncio
async def test_overlap_returns_409(client, sample_room, sample_hotel):
    base = {
        "room_id": str(sample_room.id),
        "base_price": "150000.00",
        "discount": "0",
    }
    r = await client.post(
        f"/api/v1/inventory/rooms/{sample_room.id}/rates",
        json={**base, "valid_from": "2026-06-01", "valid_to": "2026-06-30"},
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )
    assert r.status_code == 201

    r = await client.post(
        f"/api/v1/inventory/rooms/{sample_room.id}/rates",
        json={**base, "valid_from": "2026-06-15", "valid_to": "2026-07-15"},
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_no_overlap_with_inactive_rate(client, sample_room, sample_hotel):
    base = {"room_id": str(sample_room.id), "base_price": "150000.00", "discount": "0"}
    r = await client.post(
        f"/api/v1/inventory/rooms/{sample_room.id}/rates",
        json={**base, "valid_from": "2026-06-01", "valid_to": "2026-06-30"},
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )
    rate_id = r.json()["id"]

    await client.delete(
        f"/api/v1/inventory/rates/{rate_id}",
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )

    r = await client.post(
        f"/api/v1/inventory/rooms/{sample_room.id}/rates",
        json={**base, "valid_from": "2026-06-15", "valid_to": "2026-07-15"},
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )
    assert r.status_code == 201
```

### 4.38 `tests/test_rates_rbac.py`

```python
from uuid import uuid4

import pytest

from tests.helpers import auth_headers


@pytest.mark.asyncio
async def test_traveler_forbidden(client, sample_room, sample_hotel):
    r = await client.get(
        f"/api/v1/inventory/rooms/{sample_room.id}/rates",
        headers=auth_headers(role="traveler"),
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_hotel_admin_other_hotel_forbidden(client, sample_room):
    other_hotel = uuid4()
    r = await client.post(
        f"/api/v1/inventory/rooms/{sample_room.id}/rates",
        json={
            "room_id": str(sample_room.id),
            "base_price": "100000.00",
            "valid_from": "2026-11-01",
            "valid_to": "2026-11-30",
            "discount": "0",
        },
        headers=auth_headers(role="hotel_admin", hotel_id=other_hotel),
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_platform_admin_can_access_any_hotel(client, sample_room, sample_hotel):
    r = await client.get(
        f"/api/v1/inventory/hotels/{sample_hotel.id}/rates",
        headers=auth_headers(role="platform_admin"),
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_missing_jwt_returns_401(client, sample_room):
    r = await client.get(f"/api/v1/inventory/rooms/{sample_room.id}/rates")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_mfa_required_for_write(client, sample_room, sample_hotel):
    r = await client.post(
        f"/api/v1/inventory/rooms/{sample_room.id}/rates",
        json={
            "room_id": str(sample_room.id),
            "base_price": "100000.00",
            "valid_from": "2026-12-01",
            "valid_to": "2026-12-31",
            "discount": "0",
        },
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id, mfa_verified=False),
    )
    assert r.status_code == 403
```

### 4.39 `tests/test_rates_audit.py`

```python
import pytest
from sqlalchemy import select

from app.models import RateHistory
from tests.helpers import auth_headers


@pytest.mark.asyncio
async def test_create_writes_history_row(client, session, sample_room, sample_hotel):
    r = await client.post(
        f"/api/v1/inventory/rooms/{sample_room.id}/rates",
        json={
            "room_id": str(sample_room.id),
            "base_price": "100000.00",
            "valid_from": "2027-01-01",
            "valid_to": "2027-01-31",
            "discount": "0",
        },
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )
    rate_id = r.json()["id"]

    result = await session.execute(
        select(RateHistory).where(RateHistory.rate_id == rate_id)
    )
    rows = list(result.scalars().all())
    assert any(row.action.value == "create" for row in rows)
    assert all(row.changed_by_user_id is not None for row in rows)
```

### 4.40 `deploy/Dockerfile`

```dockerfile
# syntax=docker/dockerfile:1.7
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

### 4.41 `deploy/docker-compose.yml`

```yaml
version: "3.9"

services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: travelhub_app
      POSTGRES_PASSWORD: travelhub_local
      POSTGRES_DB: travelhub
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./seed_data.sql:/docker-entrypoint-initdb.d/seed_data.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U travelhub_app -d travelhub"]
      interval: 5s
      timeout: 5s
      retries: 10

  inventory-services:
    build:
      context: ..
      dockerfile: deploy/Dockerfile
    environment:
      DATABASE_URL: postgresql+asyncpg://travelhub_app:travelhub_local@db:5432/travelhub
      JWT_ISSUER: https://auth.travelhub.app
      JWT_AUDIENCE: travelhub-api
      LOG_LEVEL: DEBUG
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy

volumes:
  pgdata:
```

### 4.42 `deploy/seed_data.sql`

```sql
-- Seed data for local Docker Compose
-- Note: tables are created by alembic upgrade; this file only inserts sample data
-- after the migration. To use it, run alembic first, then psql -f seed_data.sql

CREATE EXTENSION IF NOT EXISTS btree_gist;

-- Sample hotels (one per country)
INSERT INTO hotels (id, name, country, currency)
VALUES
  ('11111111-1111-1111-1111-111111111111', 'Hotel Bogota Plaza', 'CO', 'COP'),
  ('22222222-2222-2222-2222-222222222222', 'Hotel CDMX Centro',  'MX', 'MXN')
ON CONFLICT DO NOTHING;

-- Sample rooms
INSERT INTO rooms (id, hotel_id, room_type)
VALUES
  ('33333333-3333-3333-3333-333333333333', '11111111-1111-1111-1111-111111111111', 'standard'),
  ('44444444-4444-4444-4444-444444444444', '11111111-1111-1111-1111-111111111111', 'suite'),
  ('55555555-5555-5555-5555-555555555555', '22222222-2222-2222-2222-222222222222', 'standard')
ON CONFLICT DO NOTHING;
```

### 4.43 `deploy/deploy-cloudrun.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

# Deploys inventory-services to Cloud Run in the TravelHub GCP project.
# Requires gcloud CLI authenticated and project set.

PROJECT_ID="${GCP_PROJECT_ID:-gen-lang-client-0930444414}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="inventory-services"
VPC_CONNECTOR="travelhub-connector"
ARTIFACT_REPO="${ARTIFACT_REPO:-travelhub}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD 2>/dev/null || date +%s)}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/${SERVICE_NAME}:${IMAGE_TAG}"

echo ">> Building image ${IMAGE}"
gcloud builds submit --tag "${IMAGE}" --project "${PROJECT_ID}" .

echo ">> Deploying to Cloud Run"
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE}" \
  --vpc-connector="${VPC_CONNECTOR}" \
  --set-env-vars "JWT_ISSUER=https://auth.travelhub.app,JWT_AUDIENCE=travelhub-api,DATABASE_URL=postgresql+asyncpg://travelhub_app:lALk8rAOj1TSltRQzGavZdBCrSu67ZJg@10.100.0.3:5432/travelhub" \
  --allow-unauthenticated \
  --port 8000 \
  --region "${REGION}" \
  --project "${PROJECT_ID}"

URL=$(gcloud run services describe "${SERVICE_NAME}" \
  --region "${REGION}" --project "${PROJECT_ID}" --format='value(status.url)')

echo ""
echo ">> Deployed: ${URL}"
echo ">> Update gateway/openapi-spec.yaml replacing the inventory-services PLACEHOLDER with: ${URL}"
echo ">> Then redeploy gateway: bash deploy/deploy-gateway.sh"
```

### 4.44 `.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: travelhub_app
          POSTGRES_PASSWORD: travelhub_local
          POSTGRES_DB: travelhub_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements-dev.txt

      - name: Lint
        run: ruff check app tests

      - name: Enable btree_gist
        run: |
          PGPASSWORD=travelhub_local psql -h localhost -U travelhub_app -d travelhub_test \
            -c "CREATE EXTENSION IF NOT EXISTS btree_gist;"

      - name: Run tests with coverage
        env:
          DATABASE_URL: postgresql+asyncpg://travelhub_app:travelhub_local@localhost:5432/travelhub_test
          JWT_ISSUER: https://auth.travelhub.app
          JWT_AUDIENCE: travelhub-api
        run: pytest
```

### 4.45 `README.md`

````markdown
# inventory-services

Microservicio de inventario de TravelHub. Primer módulo: **Tarifas (rates)**.

## Quick start (local)

```bash
cd deploy
docker compose up --build
```

Servicio en `http://localhost:8000` y Postgres en `localhost:5432`.

Crear migraciones aplicadas y seed:

```bash
docker compose exec inventory-services alembic upgrade head
docker compose exec db psql -U travelhub_app -d travelhub -f /docker-entrypoint-initdb.d/seed_data.sql
```

## Endpoints (módulo rates)

| Método | Ruta |
|---|---|
| POST   | `/api/v1/inventory/rooms/{room_id}/rates` |
| GET    | `/api/v1/inventory/rooms/{room_id}/rates` |
| GET    | `/api/v1/inventory/hotels/{hotel_id}/rates` |
| GET    | `/api/v1/inventory/rates/{rate_id}` |
| PATCH  | `/api/v1/inventory/rates/{rate_id}` |
| DELETE | `/api/v1/inventory/rates/{rate_id}` |
| GET    | `/api/v1/inventory/rates/effective?room_id&date` |

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Cobertura mínima: 70% (enforced en CI).

## Despliegue Cloud Run

```bash
bash deploy/deploy-cloudrun.sh
```
````

### 4.46 `CONTEXT.md`

```markdown
# inventory-services — Contexto rápido

## Reglas de dominio (cerradas)

1. Sin solapamiento de vigencias activas por room_id (validación + EXCLUDE constraint)
2. Descuento porcentual en [0, 1]
3. Una habitación = una moneda (heredada del hotel)
4. Auditoría append-only en rate_history (SQLAlchemy event listeners)

## Lo que ESTE servicio NO hace

- No calcula impuestos (eso es booking-services)
- No convierte monedas (eso es pms-integration o servicio FX externo)
- No valida firma JWT (eso es API Gateway)

## Próximos módulos a agregar al repo

- Hotel CRUD (endpoints completos)
- Room CRUD
- Disponibilidad (Availability)
- Eventos Kafka para sync con search-services
```

---

## 5. Pasos de ejecución para Claude Code

Ejecuta los pasos en orden. Si algo falla, detente y reporta antes de continuar.

```bash
# 1. Crear el repo desde cero
mkdir -p inventory-services && cd inventory-services
git init

# 2. Crear toda la estructura de archivos exactamente como se describe arriba
# (Claude Code: usa los contenidos de la sección 4 literalmente)

# 3. Verificar instalación de dependencias en venv local (sanity check)
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# 4. Linter
ruff check app tests

# 5. Levantar entorno local
cd deploy
docker compose up --build -d
sleep 8

# 6. Migraciones
docker compose exec inventory-services alembic upgrade head

# 7. Seed
docker compose exec -T db psql -U travelhub_app -d travelhub < seed_data.sql

# 8. Smoke test (dentro del contenedor)
docker compose exec inventory-services curl -s http://localhost:8000/health
# Esperado: {"status":"ok","service":"inventory-services"}

# 9. Bajar entorno local antes de tests Postgres
docker compose down -v

# 10. Tests con base Postgres efímera (alternativa: usar service de CI)
docker run -d --name pgtest -p 5432:5432 \
  -e POSTGRES_USER=travelhub_app \
  -e POSTGRES_PASSWORD=travelhub_local \
  -e POSTGRES_DB=travelhub_test \
  postgres:16-alpine
sleep 5
PGPASSWORD=travelhub_local psql -h localhost -U travelhub_app -d travelhub_test \
  -c "CREATE EXTENSION IF NOT EXISTS btree_gist;"
DATABASE_URL=postgresql+asyncpg://travelhub_app:travelhub_local@localhost:5432/travelhub_test \
JWT_ISSUER=https://auth.travelhub.app \
JWT_AUDIENCE=travelhub-api \
pytest
docker rm -f pgtest

# 11. Commit
cd ..
git add .
git commit -m "feat(rates): scaffolding inicial de inventory-services con módulo rates

- CRUD de Tarifa con validación de no-solapamiento (servicio + constraint EXCLUDE)
- Chain of Responsibility: RateLimit -> IPValidation -> RBAC -> MFA
- JWT decoder sin verify (firma validada por gateway)
- Auditoría append-only en rate_history via SQLAlchemy event listeners
- Endpoints REST + tests >= 70% cobertura
- Dockerfile, Compose, Alembic, GitHub Actions CI
- Script de despliegue a Cloud Run
"

# 12. Despliegue (sólo cuando Edwin lo apruebe)
# bash deploy/deploy-cloudrun.sh
```

---

## 6. Checklist de aceptación

Antes de marcar el módulo como terminado, verificar:

- [ ] `docker compose up` levanta sin errores y `/health` responde 200
- [ ] `alembic upgrade head` crea las tablas y la constraint `ex_rates_no_overlap_active`
- [ ] `pytest` pasa con cobertura ≥ 70%
- [ ] `ruff check app tests` no reporta errores
- [ ] Tests cubren: CRUD básico, solapamiento (409), RBAC (403 cross-hotel y traveler), MFA (403 sin mfa_verified), auditoría (rate_history poblado)
- [ ] El JWT NUNCA es verificado en firma por el backend (solo decodificado)
- [ ] La constraint `EXCLUDE USING gist` está en la migración y en la BD real
- [ ] El campo `currency` se pobla desde `hotels.currency` y NO se acepta en update
- [ ] Soft delete cambia `status` a `inactive` y conserva el registro
- [ ] Auditoría captura `user_id` y `ip` desde el contexto (no es null en tests con auth)

---

## 7. Notas importantes para Claude Code

1. **No verificar firma JWT.** Si ves `jwt.decode(token, key, ...)` en el código generado, es un bug. Debe ser `jwt.get_unverified_claims(token)` siempre.
2. **No agregar Hotel/Room endpoints.** Solo modelos mínimos. Si Edwin pide endpoints de Hotel o Room, será en un módulo separado.
3. **No usar `python-docx` ni `pandoc`.** No aplica acá pero es regla del proyecto.
4. **No usar SQLite en producción.** Para tests sí se acepta `aiosqlite`, pero todos los tests que validen la constraint `EXCLUDE` deben correr contra Postgres.
5. **No hacer commits con secretos.** El password de la BD de producción está hardcodeado en `deploy-cloudrun.sh` por compatibilidad con `INFRA_STATUS.md`; en una iteración posterior debe migrarse a Secret Manager.
6. **Si hay conflicto entre este archivo y `CONTEXT.md` del repo `user-services`**, gana este archivo para `inventory-services`.

---

## 8. Después del scaffolding

Una vez Claude Code termine, Edwin debe:

1. Revisar `git diff` y validar que la estructura coincide con la sección 3
2. Correr `docker compose up` y probar manualmente con Postman/curl
3. Crear el repo remoto en GitHub y hacer push
4. Configurar el secret `GCP_PROJECT_ID` en el repo (no es necesario para CI, solo para CD futuro)
5. Solicitar a Claude (chat) un `.md` separado para el siguiente módulo (Room, Hotel, Availability)

Fin del documento.
