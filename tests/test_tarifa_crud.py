import pytest

from tests.helpers import auth_headers


@pytest.mark.asyncio
async def test_create_tarifa_inherits_moneda(client, sample_habitacion, sample_hotel):
    payload = {
        "habitacionId": str(sample_habitacion.id),
        "precioBase": 150000.00,
        "fechaInicio": "2026-06-01T00:00:00+00:00",
        "fechaFin": "2026-06-30T23:59:59+00:00",
        "descuento": 0.10,
    }
    r = await client.post(
        f"/api/v1/inventory/habitaciones/{sample_habitacion.id}/tarifas",
        json=payload,
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["moneda"] == "COP"  # inherited from hotel.currency
    assert body["habitacionId"] == sample_habitacion.id


@pytest.mark.asyncio
async def test_create_tarifa_invalid_dates_422(client, sample_habitacion, sample_hotel):
    payload = {
        "habitacionId": str(sample_habitacion.id),
        "precioBase": 150000.00,
        "fechaInicio": "2026-06-30T00:00:00+00:00",
        "fechaFin": "2026-06-01T00:00:00+00:00",
        "descuento": 0.10,
    }
    r = await client.post(
        f"/api/v1/inventory/habitaciones/{sample_habitacion.id}/tarifas",
        json=payload,
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_get_tarifa_and_list(client, sample_habitacion, sample_hotel):
    payload = {
        "habitacionId": str(sample_habitacion.id),
        "precioBase": 200000.00,
        "fechaInicio": "2026-07-01T00:00:00+00:00",
        "fechaFin": "2026-07-31T23:59:59+00:00",
        "descuento": 0,
    }
    r = await client.post(
        f"/api/v1/inventory/habitaciones/{sample_habitacion.id}/tarifas",
        json=payload,
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )
    tarifa_id = r.json()["id"]

    r = await client.get(
        f"/api/v1/inventory/tarifas/{tarifa_id}",
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )
    assert r.status_code == 200

    r = await client.get(
        f"/api/v1/inventory/habitaciones/{sample_habitacion.id}/tarifas",
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )
    assert r.status_code == 200
    assert any(x["id"] == tarifa_id for x in r.json())


@pytest.mark.asyncio
async def test_update_tarifa_descuento(client, sample_habitacion, sample_hotel):
    payload = {
        "habitacionId": str(sample_habitacion.id),
        "precioBase": 100000.00,
        "fechaInicio": "2026-08-01T00:00:00+00:00",
        "fechaFin": "2026-08-31T23:59:59+00:00",
        "descuento": 0.05,
    }
    r = await client.post(
        f"/api/v1/inventory/habitaciones/{sample_habitacion.id}/tarifas",
        json=payload,
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )
    tarifa_id = r.json()["id"]

    r = await client.patch(
        f"/api/v1/inventory/tarifas/{tarifa_id}",
        json={"descuento": 0.20},
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )
    assert r.status_code == 200
    assert r.json()["descuento"] == 0.20


@pytest.mark.asyncio
async def test_delete_tarifa_removes_row(client, sample_habitacion, sample_hotel):
    payload = {
        "habitacionId": str(sample_habitacion.id),
        "precioBase": 100000.00,
        "fechaInicio": "2026-09-01T00:00:00+00:00",
        "fechaFin": "2026-09-30T23:59:59+00:00",
        "descuento": 0,
    }
    r = await client.post(
        f"/api/v1/inventory/habitaciones/{sample_habitacion.id}/tarifas",
        json=payload,
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )
    tarifa_id = r.json()["id"]

    r = await client.delete(
        f"/api/v1/inventory/tarifas/{tarifa_id}",
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )
    assert r.status_code == 204

    # Hard delete: la fila desaparece
    r = await client.get(
        f"/api/v1/inventory/tarifas/{tarifa_id}",
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_vigente_returns_precio_final(client, sample_habitacion, sample_hotel):
    payload = {
        "habitacionId": str(sample_habitacion.id),
        "precioBase": 100000.00,
        "fechaInicio": "2026-10-01T00:00:00+00:00",
        "fechaFin": "2026-10-31T23:59:59+00:00",
        "descuento": 0.25,
    }
    await client.post(
        f"/api/v1/inventory/habitaciones/{sample_habitacion.id}/tarifas",
        json=payload,
        headers=auth_headers(role="hotel_admin", hotel_id=sample_hotel.id),
    )

    r = await client.get(
        "/api/v1/inventory/tarifas/vigente",
        params={"habitacion_id": str(sample_habitacion.id), "fecha": "2026-10-15T12:00:00+00:00"},
        headers=auth_headers(role="platform_admin"),
    )
    assert r.status_code == 200
    assert r.json()["precioFinal"] == 75000.00
