import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models import RateHistory
from tests.helpers import auth_headers


@pytest.mark.asyncio
async def test_create_writes_history_row(client, engine, sample_habitacion, sample_hotel):
    r = await client.post(
        f"/api/v1/inventory/habitaciones/{sample_habitacion.id}/rates",
        json={
            "habitacionId": str(sample_habitacion.id),
            "base_price": "100000.00",
            "valid_from": "2027-01-01",
            "valid_to": "2027-01-31",
            "discount": "0",
        },
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )
    rate_id = r.json()["id"]

    # Inline session so its connection is opened/closed within the test loop,
    # avoiding the cross-loop teardown issue of the shared `session` fixture.
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as s:
        result = await s.execute(
            select(RateHistory).where(RateHistory.rate_id == rate_id)
        )
        rows = list(result.scalars().all())

    assert any(row.action.value == "create" for row in rows)
    assert all(row.changed_by_user_id is not None for row in rows)
