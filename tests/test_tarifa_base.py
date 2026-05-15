"""Tests del endpoint GET /habitaciones/{id}/tarifas/base.

Devuelve LA tarifa base (descuento=0) vigente para una fecha, aplicando la
misma regla de "rango más estrecho gana" pero filtrando solo bases.
"""
import pytest

from tests.helpers import auth_headers


@pytest.mark.asyncio
async def test_get_base_devuelve_la_base_vigente(client, sample_habitacion, sample_hotel):
    """Una sola base anual → es la que devuelve /base."""
    hdr = auth_headers(role="hotel_admin", hotel_id=sample_hotel.id)
    url_create = f"/api/v1/inventory/habitaciones/{sample_habitacion.id}/tarifas"
    await client.post(url_create, json={
        "habitacionId": str(sample_habitacion.id),
        "precioBase": 150.0,
        "fechaInicio": "2029-01-01T00:00:00+00:00",
        "fechaFin": "2029-12-31T23:59:59+00:00",
        "descuento": 0,
    }, headers=hdr)

    r = await client.get(
        f"/api/v1/inventory/habitaciones/{sample_habitacion.id}/tarifas/base",
        params={"fecha": "2029-05-15T12:00:00+00:00"},
        headers=hdr,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["precioBase"] == pytest.approx(150.0)
    assert body["descuento"] == pytest.approx(0)


@pytest.mark.asyncio
async def test_get_base_ignora_promos(client, sample_habitacion, sample_hotel):
    """Aunque haya promo vigente, /base ignora promos y devuelve la base."""
    hdr = auth_headers(role="hotel_admin", hotel_id=sample_hotel.id)
    url_create = f"/api/v1/inventory/habitaciones/{sample_habitacion.id}/tarifas"

    await client.post(url_create, json={
        "habitacionId": str(sample_habitacion.id),
        "precioBase": 200.0,
        "fechaInicio": "2030-01-01T00:00:00+00:00",
        "fechaFin": "2030-12-31T23:59:59+00:00",
        "descuento": 0,
    }, headers=hdr)
    await client.post(url_create, json={
        "habitacionId": str(sample_habitacion.id),
        "precioBase": 200.0,
        "fechaInicio": "2030-07-01T00:00:00+00:00",
        "fechaFin": "2030-07-15T23:59:59+00:00",
        "descuento": 0.40,
    }, headers=hdr)

    # Durante la promo: /vigente devuelve la promo, pero /base devuelve la base
    r = await client.get(
        "/api/v1/inventory/tarifas/vigente",
        params={"habitacion_id": str(sample_habitacion.id), "fecha": "2030-07-10T12:00:00+00:00"},
        headers=auth_headers(role="platform_admin"),
    )
    assert r.json()["descuento"] == pytest.approx(0.40)

    r = await client.get(
        f"/api/v1/inventory/habitaciones/{sample_habitacion.id}/tarifas/base",
        params={"fecha": "2030-07-10T12:00:00+00:00"},
        headers=hdr,
    )
    assert r.status_code == 200
    assert r.json()["descuento"] == pytest.approx(0)
    assert r.json()["precioBase"] == pytest.approx(200.0)


@pytest.mark.asyncio
async def test_get_base_dos_bases_devuelve_la_mas_estrecha(
    client, sample_habitacion, sample_hotel
):
    """Base anual + base trimestral prospectiva → /base devuelve la trimestral."""
    hdr = auth_headers(role="hotel_admin", hotel_id=sample_hotel.id)
    url_create = f"/api/v1/inventory/habitaciones/{sample_habitacion.id}/tarifas"

    await client.post(url_create, json={
        "habitacionId": str(sample_habitacion.id),
        "precioBase": 150.0,
        "fechaInicio": "2031-01-01T00:00:00+00:00",
        "fechaFin": "2031-12-31T23:59:59+00:00",
        "descuento": 0,
    }, headers=hdr)
    await client.post(url_create, json={
        "habitacionId": str(sample_habitacion.id),
        "precioBase": 165.0,
        "fechaInicio": "2031-04-01T00:00:00+00:00",
        "fechaFin": "2031-12-31T23:59:59+00:00",
        "descuento": 0,
    }, headers=hdr)

    # Mayo (cubierto por ambas): devuelve la trimestral
    r = await client.get(
        f"/api/v1/inventory/habitaciones/{sample_habitacion.id}/tarifas/base",
        params={"fecha": "2031-05-15T12:00:00+00:00"},
        headers=hdr,
    )
    assert r.status_code == 200
    assert r.json()["precioBase"] == pytest.approx(165.0)

    # Febrero (solo cubierto por la anual): devuelve la anual
    r = await client.get(
        f"/api/v1/inventory/habitaciones/{sample_habitacion.id}/tarifas/base",
        params={"fecha": "2031-02-15T12:00:00+00:00"},
        headers=hdr,
    )
    assert r.status_code == 200
    assert r.json()["precioBase"] == pytest.approx(150.0)


@pytest.mark.asyncio
async def test_get_base_404_si_no_existe(client, sample_habitacion, sample_hotel):
    """Sin tarifas → 404 'Tarifa no encontrada'."""
    hdr = auth_headers(role="hotel_admin", hotel_id=sample_hotel.id)
    r = await client.get(
        f"/api/v1/inventory/habitaciones/{sample_habitacion.id}/tarifas/base",
        headers=hdr,
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_base_404_si_solo_hay_promos(client, sample_habitacion, sample_hotel):
    """Si solo hay promos (descuento>0) sin base, /base devuelve 404."""
    hdr = auth_headers(role="hotel_admin", hotel_id=sample_hotel.id)
    url_create = f"/api/v1/inventory/habitaciones/{sample_habitacion.id}/tarifas"

    await client.post(url_create, json={
        "habitacionId": str(sample_habitacion.id),
        "precioBase": 100.0,
        "fechaInicio": "2032-01-01T00:00:00+00:00",
        "fechaFin": "2032-01-31T23:59:59+00:00",
        "descuento": 0.25,
    }, headers=hdr)

    r = await client.get(
        f"/api/v1/inventory/habitaciones/{sample_habitacion.id}/tarifas/base",
        params={"fecha": "2032-01-15T12:00:00+00:00"},
        headers=hdr,
    )
    assert r.status_code == 404
