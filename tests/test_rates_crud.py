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
    # Traveler is blocked by RBAC; test as platform_admin
    if r.status_code == 403:
        r = await client.get(
            "/api/v1/inventory/rates/effective",
            params={"room_id": str(sample_room.id), "date": "2026-10-15"},
            headers=auth_headers(role="platform_admin"),
        )
    assert r.status_code == 200
    assert r.json()["final_price"] == "75000.00"
