"""Resolución de tarifas con overlap (modelo de promos 2026-05-14).

Reglas:
- Múltiples tarifas pueden solapar para la misma habitación.
- /vigente elige por: rango más estrecho gana, desempate por fechaInicio más reciente.
"""
import pytest

from tests.helpers import auth_headers

BASE_INICIO = "2026-06-01T00:00:00+00:00"
BASE_FIN = "2026-12-31T23:59:59+00:00"
PROMO_INICIO = "2026-11-28T00:00:00+00:00"
PROMO_FIN = "2026-11-30T23:59:59+00:00"


@pytest.mark.asyncio
async def test_promo_overrides_base_en_su_rango(client, sample_habitacion, sample_hotel):
    """Base anual + promo 3 días → promo gana en sus 3 días."""
    hdr = auth_headers(role="hotel_admin", hotel_id=sample_hotel.id)
    url_create = f"/api/v1/inventory/habitaciones/{sample_habitacion.id}/tarifas"

    # Base anual con descuento 0
    r = await client.post(url_create, json={
        "habitacionId": str(sample_habitacion.id),
        "precioBase": 150.0,
        "fechaInicio": BASE_INICIO,
        "fechaFin": BASE_FIN,
        "descuento": 0,
    }, headers=hdr)
    assert r.status_code == 201

    # Promo Black Friday (3 días, 30% off)
    r = await client.post(url_create, json={
        "habitacionId": str(sample_habitacion.id),
        "precioBase": 150.0,
        "fechaInicio": PROMO_INICIO,
        "fechaFin": PROMO_FIN,
        "descuento": 0.30,
    }, headers=hdr)
    assert r.status_code == 201

    # Vigente en pleno BF: gana la promo
    r = await client.get(
        "/api/v1/inventory/tarifas/vigente",
        params={"habitacion_id": str(sample_habitacion.id), "fecha": "2026-11-29T12:00:00+00:00"},
        headers=auth_headers(role="platform_admin"),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["descuento"] == pytest.approx(0.30)
    assert body["precioFinal"] == pytest.approx(105.0)  # 150 * 0.7

    # Fuera de BF: gana base
    r = await client.get(
        "/api/v1/inventory/tarifas/vigente",
        params={"habitacion_id": str(sample_habitacion.id), "fecha": "2026-07-15T12:00:00+00:00"},
        headers=auth_headers(role="platform_admin"),
    )
    assert r.status_code == 200
    assert r.json()["descuento"] == pytest.approx(0)
    assert r.json()["precioFinal"] == pytest.approx(150.0)


@pytest.mark.asyncio
async def test_subir_precio_base_prospectivo(client, sample_habitacion, sample_hotel):
    """Base anual 150 + nueva base trimestral 165 (más estrecha) → trimestral gana en su rango."""
    hdr = auth_headers(role="hotel_admin", hotel_id=sample_hotel.id)
    url_create = f"/api/v1/inventory/habitaciones/{sample_habitacion.id}/tarifas"

    await client.post(url_create, json={
        "habitacionId": str(sample_habitacion.id),
        "precioBase": 150.0,
        "fechaInicio": "2027-01-01T00:00:00+00:00",
        "fechaFin": "2027-12-31T23:59:59+00:00",
        "descuento": 0,
    }, headers=hdr)

    await client.post(url_create, json={
        "habitacionId": str(sample_habitacion.id),
        "precioBase": 165.0,
        "fechaInicio": "2027-04-01T00:00:00+00:00",
        "fechaFin": "2027-12-31T23:59:59+00:00",
        "descuento": 0,
    }, headers=hdr)

    # Mayo: dentro de los dos rangos, gana el más estrecho (trimestral)
    r = await client.get(
        "/api/v1/inventory/tarifas/vigente",
        params={"habitacion_id": str(sample_habitacion.id), "fecha": "2027-05-15T12:00:00+00:00"},
        headers=auth_headers(role="platform_admin"),
    )
    assert r.status_code == 200
    assert r.json()["precioFinal"] == pytest.approx(165.0)

    # Febrero: solo aplica la base anual
    r = await client.get(
        "/api/v1/inventory/tarifas/vigente",
        params={"habitacion_id": str(sample_habitacion.id), "fecha": "2027-02-15T12:00:00+00:00"},
        headers=auth_headers(role="platform_admin"),
    )
    assert r.status_code == 200
    assert r.json()["precioFinal"] == pytest.approx(150.0)


@pytest.mark.asyncio
async def test_dos_promos_solapadas_gana_la_mas_estrecha(client, sample_habitacion, sample_hotel):
    """Promo 1 semana + promo de 1 día dentro → la de 1 día gana en su día."""
    hdr = auth_headers(role="hotel_admin", hotel_id=sample_hotel.id)
    url_create = f"/api/v1/inventory/habitaciones/{sample_habitacion.id}/tarifas"

    # Promo semana 30% off
    await client.post(url_create, json={
        "habitacionId": str(sample_habitacion.id),
        "precioBase": 100.0,
        "fechaInicio": "2028-06-01T00:00:00+00:00",
        "fechaFin": "2028-06-07T23:59:59+00:00",
        "descuento": 0.30,
    }, headers=hdr)

    # Flash 1 día 50% off
    await client.post(url_create, json={
        "habitacionId": str(sample_habitacion.id),
        "precioBase": 100.0,
        "fechaInicio": "2028-06-03T00:00:00+00:00",
        "fechaFin": "2028-06-03T23:59:59+00:00",
        "descuento": 0.50,
    }, headers=hdr)

    # En el día del flash: gana flash (50%)
    r = await client.get(
        "/api/v1/inventory/tarifas/vigente",
        params={"habitacion_id": str(sample_habitacion.id), "fecha": "2028-06-03T12:00:00+00:00"},
        headers=auth_headers(role="platform_admin"),
    )
    assert r.status_code == 200
    assert r.json()["precioFinal"] == pytest.approx(50.0)  # 100 * 0.5

    # Otro día de la semana: gana semanal (30%)
    r = await client.get(
        "/api/v1/inventory/tarifas/vigente",
        params={"habitacion_id": str(sample_habitacion.id), "fecha": "2028-06-05T12:00:00+00:00"},
        headers=auth_headers(role="platform_admin"),
    )
    assert r.status_code == 200
    assert r.json()["precioFinal"] == pytest.approx(70.0)  # 100 * 0.7
