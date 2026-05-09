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
