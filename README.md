# inventory-services

Microservicio de inventario de TravelHub. Primer módulo: **Tarifas (rates)**.

## Quick start (local)

```bash
cd deploy
docker compose up --build
```

Servicio en `http://localhost:8000` y Postgres en `localhost:5432`.

Crear migraciones aplicadas y seed:

```bash
docker compose exec inventory-services alembic upgrade head
docker compose exec db psql -U travelhub_app -d travelhub -f /docker-entrypoint-initdb.d/seed_data.sql
```

## Endpoints (módulo rates)

| Método | Ruta |
|---|---|
| POST   | `/api/v1/inventory/rooms/{room_id}/rates` |
| GET    | `/api/v1/inventory/rooms/{room_id}/rates` |
| GET    | `/api/v1/inventory/hotels/{hotel_id}/rates` |
| GET    | `/api/v1/inventory/rates/effective?room_id&date` |
| GET    | `/api/v1/inventory/rates/{rate_id}` |
| PATCH  | `/api/v1/inventory/rates/{rate_id}` |
| DELETE | `/api/v1/inventory/rates/{rate_id}` |

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Cobertura mínima: 70% (enforced en CI).

## Despliegue Cloud Run

```bash
bash deploy/deploy-cloudrun.sh
```
