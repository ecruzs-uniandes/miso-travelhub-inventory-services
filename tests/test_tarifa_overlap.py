import pytest

from tests.helpers import auth_headers

JUNE_START = "2026-06-01T00:00:00+00:00"
JUNE_END = "2026-06-30T23:59:59+00:00"
MID_JUNE_START = "2026-06-15T00:00:00+00:00"
JULY_MID_END = "2026-07-15T23:59:59+00:00"


@pytest.mark.asyncio
async def test_overlap_returns_409(client, sample_habitacion, sample_hotel):
    base = {
        "habitacionId": str(sample_habitacion.id),
        "precioBase": 150000.00,
        "descuento": 0,
    }
    r = await client.post(
        f"/api/v1/inventory/habitaciones/{sample_habitacion.id}/tarifas",
        json={**base, "fechaInicio": JUNE_START, "fechaFin": JUNE_END},
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )
    assert r.status_code == 201

    r = await client.post(
        f"/api/v1/inventory/habitaciones/{sample_habitacion.id}/tarifas",
        json={**base, "fechaInicio": MID_JUNE_START, "fechaFin": JULY_MID_END},
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_no_overlap_after_delete(client, sample_habitacion, sample_hotel):
    """Tras un DELETE real, el rango queda libre — el siguiente create no debe colisionar."""
    base = {
        "habitacionId": str(sample_habitacion.id),
        "precioBase": 150000.00,
        "descuento": 0,
    }
    r = await client.post(
        f"/api/v1/inventory/habitaciones/{sample_habitacion.id}/tarifas",
        json={**base, "fechaInicio": JUNE_START, "fechaFin": JUNE_END},
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )
    tarifa_id = r.json()["id"]

    await client.delete(
        f"/api/v1/inventory/tarifas/{tarifa_id}",
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )

    r = await client.post(
        f"/api/v1/inventory/habitaciones/{sample_habitacion.id}/tarifas",
        json={**base, "fechaInicio": MID_JUNE_START, "fechaFin": JULY_MID_END},
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )
    assert r.status_code == 201
