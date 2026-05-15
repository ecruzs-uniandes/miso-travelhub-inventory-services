# inventory-services

Microservicio de inventario de TravelHub. Módulo: **Tarifas** (tabla canonical `tarifa`).

## Quick start (local)

Usa el `docker-compose.yml` del monorepo en `../travelhub-local/`:

```bash
cd ../travelhub-local
docker compose up -d
# Servicio en http://localhost:8004 (no 8000 — port mapping del monorepo)
# Postgres en host:5433 → container:5432, DB travelhub_pms
```

Schema canonical creado por `travelhub-local/scripts/init-db.sql` con seed (1 hotel + 3 habitaciones + 7 días de disponibilidad).

## Endpoints (módulo tarifa)

Prefijo: `/api/v1/inventory`. Auth: JWT Bearer (decode no-verify, gateway ya verificó).

| Método | Ruta | Descripción |
|---|---|---|
| POST   | `/habitaciones/{habitacion_id}/tarifas` | Crear tarifa. Moneda heredada de `hotel.currency`. Acepta solapamientos (base + promos). |
| GET    | `/habitaciones/{habitacion_id}/tarifas` | Listar todas (base + promos) de una habitación |
| GET    | `/habitaciones/{habitacion_id}/tarifas/base?fecha=<ISO>` | **Base vigente** (descuento=0). Ignora promos. Para el front del admin |
| GET    | `/hoteles/{hotel_id}/tarifas` | Listar todas las tarifas de un hotel |
| GET    | `/tarifas/vigente?habitacion_id=<id>&fecha=<ISO>` | Tarifa **vigente** (incluye promos) con `precioFinal` calculado |
| GET    | `/tarifas/{tarifa_id}` | Detalle |
| PATCH  | `/tarifas/{tarifa_id}` | Actualizar campos parciales |
| DELETE | `/tarifas/{tarifa_id}` | **Hard delete** — audit row queda en `tarifa_history` |

### Schema body (POST/PATCH)

```json
{
  "habitacionId": "b1000000-0000-0000-0000-000000000001",
  "precioBase": 150000.0,
  "fechaInicio": "2026-06-01T00:00:00+00:00",
  "fechaFin": "2026-06-30T23:59:59+00:00",
  "descuento": 0.10
}
```

- `precioBase`, `descuento`: `double precision` (no decimal); `descuento ∈ [0, 1]` (no porcentual 0-100)
- `fechaInicio`, `fechaFin`: `timestamptz` (ISO 8601 con zona)
- `moneda` se ignora en el body — siempre hereda de `hotel.currency`

### Reglas de dominio (modelo de promos, desde 2026-05-14)

1. **Overlap permitido**: múltiples tarifas pueden cubrir el mismo rango para una habitación. Convención: `descuento=0` es base, `descuento>0` es promo. No hay constraint EXCLUDE.
2. **Resolución `/vigente`**: "rango más estrecho gana, fechaInicio más reciente como desempate".
   - Base anual + promo 3 días → promo gana en su rango
   - Base anual + base trimestral (cambio prospectivo) → trimestral gana
   - Para subir base: crear nueva fila con rango más corto
3. **`/base`** ignora promos — el front del admin lo usa para mostrar la base actual y editarla.
4. `descuento ∈ [0, 1]`, `precioBase > 0`, `fechaInicio ≤ fechaFin` (CheckConstraints).
5. `tarifa.moneda` se hereda de `hotel.currency` (`Hotel` ↔ `Habitacion` ↔ `Tarifa`).
6. Auditoría append-only en `tarifa_history` via SQLAlchemy event listeners.

## Tests

```bash
pip install -r requirements-dev.txt
DATABASE_URL=postgresql+asyncpg://travelhub_app:travelhub_local_pass@localhost:5433/travelhub_test \
JWT_ISSUER=https://auth.travelhub.app \
JWT_AUDIENCE=travelhub-api \
KAFKA_ENABLED=false \
pytest
```

16 tests pasando. Cobertura mínima: 70% (enforced en CI).

## Despliegue Cloud Run

CI/CD automático: push a `feature/**` o `develop` → tests + lint + deploy DEV. Push a `main` → canary PROD (10→50→100, requireApproval). Ver `.github/workflows/ci.yml`.

Manual:
```bash
bash deploy/deploy-cloudrun.sh dev    # o prod
```
