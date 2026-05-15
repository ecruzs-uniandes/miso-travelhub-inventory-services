import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models import TarifaHistory
from tests.helpers import auth_headers


@pytest.mark.asyncio
async def test_create_writes_history_row(client, engine, sample_habitacion, sample_hotel):
    r = await client.post(
        f"/api/v1/inventory/habitaciones/{sample_habitacion.id}/tarifas",
        json={
            "habitacionId": str(sample_habitacion.id),
            "precioBase": 100000.00,
            "fechaInicio": "2027-01-01T00:00:00+00:00",
            "fechaFin": "2027-01-31T23:59:59+00:00",
            "descuento": 0,
        },
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )
    tarifa_id = r.json()["id"]

    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as s:
        result = await s.execute(
            select(TarifaHistory).where(TarifaHistory.tarifa_id == tarifa_id)
        )
        rows = list(result.scalars().all())

    assert any(row.action.value == "create" for row in rows)
    assert all(row.changed_by_user_id is not None for row in rows)


@pytest.mark.asyncio
async def test_delete_writes_history_row(client, engine, sample_habitacion, sample_hotel):
    """Hard delete debe dejar entry en tarifa_history con action=delete."""
    r = await client.post(
        f"/api/v1/inventory/habitaciones/{sample_habitacion.id}/tarifas",
        json={
            "habitacionId": str(sample_habitacion.id),
            "precioBase": 80000.00,
            "fechaInicio": "2027-02-01T00:00:00+00:00",
            "fechaFin": "2027-02-28T23:59:59+00:00",
            "descuento": 0,
        },
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )
    tarifa_id = r.json()["id"]

    r = await client.delete(
        f"/api/v1/inventory/tarifas/{tarifa_id}",
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )
    assert r.status_code == 204

    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as s:
        result = await s.execute(
            select(TarifaHistory).where(TarifaHistory.tarifa_id == tarifa_id)
        )
        rows = list(result.scalars().all())

    actions = {row.action.value for row in rows}
    assert "create" in actions
    assert "delete" in actions
