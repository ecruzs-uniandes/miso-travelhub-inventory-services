# inventory-services

Microservicio de inventario de TravelHub. Módulo principal: **Tarifas** (tabla canonical `tarifa`). Expone también un listado read-only de **habitaciones por hotel** (`/hoteles/{id}/habitaciones`) como entry point del flujo admin — el owner real de `habitacion` sigue siendo `search-service`.

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

Prefijo: `/api/v1/inventory`. Auth: JWT Bearer (decode no-verify, gateway ya verificó) **excepto** los 2 endpoints públicos marcados abajo.

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| POST   | `/habitaciones/{habitacion_id}/tarifas` | `hotel_admin`/`platform_admin` + MFA | Crear tarifa. Moneda heredada de `hotel.currency`. Acepta solapamientos (base + promos). |
| GET    | `/habitaciones/{habitacion_id}/tarifas` | `hotel_admin`/`platform_admin` | Listar todas (base + promos) de una habitación |
| GET    | `/habitaciones/{habitacion_id}/tarifas/base?fecha=<ISO>` | **público** | **Base vigente** (descuento=0). Ignora promos. Lo consume el front del admin y también el viajero anónimo en página de detalle. |
| GET    | `/hoteles/{hotel_id}/tarifas` | `hotel_admin`/`platform_admin` | Listar todas las tarifas de un hotel |
| GET    | `/hoteles/{hotel_id}/habitaciones` | `hotel_admin`/`platform_admin` | Listar habitaciones de un hotel (vista admin). Read-only — inventory NO es owner, solo expone el listado para que el front pinte "mis habitaciones" y luego entre al CRUD de tarifas. |
| GET    | `/tarifas/vigente?habitacion_id=<id>&fecha=<ISO>` | **público** | Tarifa **vigente** (incluye promos) con `precioFinal` calculado. Lo consume el viajero anónimo antes de registrarse. |
| GET    | `/tarifas/{tarifa_id}` | `hotel_admin`/`platform_admin` | Detalle |
| PATCH  | `/tarifas/{tarifa_id}` | `hotel_admin`/`platform_admin` + MFA | Actualizar campos parciales |
| DELETE | `/tarifas/{tarifa_id}` | `hotel_admin`/`platform_admin` + MFA | **Hard delete** — audit row queda en `tarifa_history` |

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
7. **MFA requerido** en write operations (POST/PATCH/DELETE) para `hotel_admin`. El JWT debe traer `mfa_verified=true`.

### Operativa del hotel_admin (flujo de UI)

```
0. Listar habitaciones de mi hotel (entry point del admin):
   GET /hoteles/{mi_hotel_id}/habitaciones
   → array de habitaciones; el front pinta la grid y el admin selecciona una

1. Abrir editor de tarifas para "Suite 002":
   GET /habitaciones/b1.../tarifas/base
   → muestra precioBase=150, fechaInicio=2026-01-01, fechaFin=2026-12-31 (base anual)

2. Cambiar precio base SOLO desde abril (cambio prospectivo):
   POST /habitaciones/b1.../tarifas
   { "habitacionId": "b1...", "precioBase": 165, "descuento": 0,
     "fechaInicio": "2026-04-01T00:00:00Z", "fechaFin": "2026-12-31T23:59:59Z" }
   → Nueva base trimestral. La anual sigue, pero pierde por rango más estrecho.

3. Agregar promo Black Friday 30% (3 días):
   POST /habitaciones/b1.../tarifas
   { "habitacionId": "b1...", "precioBase": 165, "descuento": 0.30,
     "fechaInicio": "2026-11-28T00:00:00Z", "fechaFin": "2026-11-30T23:59:59Z" }
   → Promo independiente; base anual sigue intacta.

4. Cancelar la promo:
   DELETE /tarifas/{promo_id}    → 204, audit row en tarifa_history.

5. Ver listado completo para auditoría:
   GET /habitaciones/b1.../tarifas
   → array con base anual + base trimestral + cualquier promo viva. El front
     filtra por descuento==0 (bases) y descuento>0 (promos).
```

### Cálculo del precio final

`precioFinal = round(precioBase * (1 - descuento), 2)`

Lo calcula el backend en `Tarifa.calcular_precio_final()` y lo devuelve en `/vigente`. El front no calcula nada — solo renderiza. Si quiere mostrar "tachado/promo" usa los campos `precioBase` y `descuento` que también vienen en la respuesta.

### Eventos Kafka publicados

Topic `inventory-rate-events` (3 particiones, key = `hotel_id`):

| event_type | Trigger | Payload |
|---|---|---|
| `tarifa_created` | POST exitoso | `{event_id, hotel_id, habitacion_id, tarifa_id, precio_base, moneda, descuento, precio_final, fecha_inicio, fecha_fin, timestamp}` |
| `tarifa_updated` | PATCH exitoso | igual |
| `tarifa_deleted` | DELETE exitoso (antes del hard delete) | igual |

Configurable via `KAFKA_ENABLED=false` (deshabilita producer; tests + local sin kafka).

## Tests

```bash
pip install -r requirements-dev.txt
DATABASE_URL=postgresql+asyncpg://travelhub_app:travelhub_local_pass@localhost:5433/travelhub_test \
JWT_ISSUER=https://auth.travelhub.app \
JWT_AUDIENCE=travelhub-api \
KAFKA_ENABLED=false \
pytest
```

29 tests pasando. Mínimo enforced en CI: 70% cobertura.

Suites:
- `test_health.py` — health endpoint
- `test_tarifa_crud.py` — POST/GET/PATCH/DELETE happy path + 404
- `test_tarifa_overlap.py` — modelo de promos: promo over base, subir base prospectivo, dos promos solapadas
- `test_tarifa_base.py` — endpoint `/base`: con/sin fecha, ignora promos, multi-base, 404
- `test_tarifa_rbac.py` — RBAC: traveler 403, hotel_admin cross-hotel 403, MFA requerido para write
- `test_tarifa_audit.py` — audit row en `tarifa_history` para create/update/delete
- `test_habitacion_list.py` — listado de habitaciones por hotel: RBAC, hotel sin habitaciones, orden por tipo

## Despliegue Cloud Run

CI/CD automático: push a `feature/**` o `develop` → tests + lint + deploy DEV. Push a `main` → canary PROD (10→50→100, requireApproval). Ver `.github/workflows/ci.yml`.

Manual:
```bash
bash deploy/deploy-cloudrun.sh dev    # o prod
```

## Más docs

- [`CLAUDE.md`](./CLAUDE.md) — contexto profundo: network setup GCP, secrets, deploy gotchas
- [`../PMS_DATA_MODEL.md`](../PMS_DATA_MODEL.md) — sección "Modelo de tarifas + promociones" con escenarios, SQL de resolución, mapping legacy → canonical
- [`../CONTEXT_ROOT.md`](../CONTEXT_ROOT.md) — mapa global del monorepo TravelHub
