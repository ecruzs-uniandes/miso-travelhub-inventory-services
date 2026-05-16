"""Tests del endpoint GET /api/v1/inventory/hoteles/{hotel_id}/habitaciones.

Es lectura read-only para el front del admin. RBAC: hotel_admin solo su hotel,
platform_admin cualquiera. Hotel sin habitaciones → [].
"""
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Habitacion, Hotel
from tests.helpers import auth_headers


@pytest.mark.asyncio
async def test_hotel_admin_lists_own_hotel(client, sample_habitacion, sample_hotel):
    r = await client.get(
        f"/api/v1/inventory/hoteles/{sample_hotel.id}/habitaciones",
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    h = body[0]
    assert h["id"] == sample_habitacion.id
    assert h["hotelId"] == sample_hotel.id
    assert h["tipo"] == "Doble"
    assert h["capacidadMaxima"] == 2


@pytest.mark.asyncio
async def test_hotel_admin_other_hotel_forbidden(client, sample_hotel):
    other_hotel = str(uuid4())
    r = await client.get(
        f"/api/v1/inventory/hoteles/{sample_hotel.id}/habitaciones",
        headers=auth_headers(role="hotel_admin", hotel_id=other_hotel),
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_platform_admin_can_list_any_hotel(client, sample_habitacion, sample_hotel):
    r = await client.get(
        f"/api/v1/inventory/hoteles/{sample_hotel.id}/habitaciones",
        headers=auth_headers(role="platform_admin"),
    )
    assert r.status_code == 200
    assert len(r.json()) == 1


@pytest.mark.asyncio
async def test_traveler_forbidden(client, sample_hotel):
    r = await client.get(
        f"/api/v1/inventory/hoteles/{sample_hotel.id}/habitaciones",
        headers=auth_headers(role="traveler"),
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_missing_jwt_returns_401(client, sample_hotel):
    r = await client.get(f"/api/v1/inventory/hoteles/{sample_hotel.id}/habitaciones")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_hotel_without_habitaciones_returns_empty_list(client, session: AsyncSession):
    empty_hotel = Hotel(id=str(uuid4()), currency="USD")
    session.add(empty_hotel)
    await session.commit()
    r = await client.get(
        f"/api/v1/inventory/hoteles/{empty_hotel.id}/habitaciones",
        headers=auth_headers(role="platform_admin"),
    )
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_multiple_habitaciones_ordered_by_tipo(
    client, session: AsyncSession, sample_hotel: Hotel
):
    """Las habitaciones se devuelven ordenadas por tipo (alfabético) — útil para que
    el front pinte la grid sin tener que sortear el mismo orden cada vez."""
    suite = Habitacion(
        id=str(uuid4()),
        hotelId=sample_hotel.id,
        tipo="Suite",
        categoria="Premium",
        capacidadMaxima=4,
        descripcion="Suite con vista",
        imagenes=[],
        tipo_habitacion="suite",
        tipo_cama=["king"],
        tamano_habitacion="60m2",
        amenidades=["AC", "minibar"],
    )
    sencilla = Habitacion(
        id=str(uuid4()),
        hotelId=sample_hotel.id,
        tipo="Individual",
        categoria="Standard",
        capacidadMaxima=1,
        descripcion="Habitación sencilla",
        imagenes=[],
        tipo_habitacion="standard",
        tipo_cama=["single"],
        tamano_habitacion="18m2",
        amenidades=["AC"],
    )
    session.add_all([suite, sencilla])
    await session.commit()

    r = await client.get(
        f"/api/v1/inventory/hoteles/{sample_hotel.id}/habitaciones",
        headers=auth_headers(role="platform_admin"),
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    tipos = [h["tipo"] for h in body]
    assert tipos == ["Individual", "Suite"]
