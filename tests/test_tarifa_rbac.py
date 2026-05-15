from uuid import uuid4

import pytest

from tests.helpers import auth_headers


@pytest.mark.asyncio
async def test_traveler_forbidden(client, sample_habitacion, sample_hotel):
    r = await client.get(
        f"/api/v1/inventory/habitaciones/{sample_habitacion.id}/tarifas",
        headers=auth_headers(role="traveler"),
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_hotel_admin_other_hotel_forbidden(client, sample_habitacion):
    other_hotel = uuid4()
    r = await client.post(
        f"/api/v1/inventory/habitaciones/{sample_habitacion.id}/tarifas",
        json={
            "habitacionId": str(sample_habitacion.id),
            "precioBase": 100000.00,
            "fechaInicio": "2026-11-01T00:00:00+00:00",
            "fechaFin": "2026-11-30T23:59:59+00:00",
            "descuento": 0,
        },
        headers=auth_headers(role="hotel_admin", hotel_id=other_hotel),
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_platform_admin_can_access_any_hotel(client, sample_habitacion, sample_hotel):
    r = await client.get(
        f"/api/v1/inventory/hoteles/{sample_hotel.id}/tarifas",
        headers=auth_headers(role="platform_admin"),
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_missing_jwt_returns_401(client, sample_habitacion):
    r = await client.get(f"/api/v1/inventory/habitaciones/{sample_habitacion.id}/tarifas")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_mfa_required_for_write(client, sample_habitacion, sample_hotel):
    r = await client.post(
        f"/api/v1/inventory/habitaciones/{sample_habitacion.id}/tarifas",
        json={
            "habitacionId": str(sample_habitacion.id),
            "precioBase": 100000.00,
            "fechaInicio": "2026-12-01T00:00:00+00:00",
            "fechaFin": "2026-12-31T23:59:59+00:00",
            "descuento": 0,
        },
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id, mfa_verified=False),
    )
    assert r.status_code == 403
