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
