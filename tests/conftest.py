import os
from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.audit.listeners import register_rate_audit_listeners
from app.database import get_db
from app.main import app
from app.models import Base, Hotel, Room

# Read from DATABASE_URL env var so CI password matches the postgres service.
# Fallback to local dev defaults when running outside CI.
TEST_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://travelhub_app:travelhub_local@localhost:5432/travelhub_test",
)


@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(TEST_DB_URL, poolclass=NullPool)
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
