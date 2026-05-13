# inventory-services — Contexto rápido

## Reglas de dominio (cerradas)

1. Sin solapamiento de vigencias activas por room_id (validación + EXCLUDE constraint)
2. Descuento porcentual en [0, 1]
3. Una habitación = una moneda (heredada del hotel)
4. Auditoría append-only en rate_history (SQLAlchemy event listeners)

## Lo que ESTE servicio NO hace

- No calcula impuestos (eso es booking-services)
- No convierte monedas (eso es pms-integration o servicio FX externo)
- No valida firma JWT (eso es API Gateway)

## Próximos módulos a agregar al repo

- Hotel CRUD (endpoints completos)
- Room CRUD
- Disponibilidad (Availability)
- Eventos Kafka para sync con search-services
