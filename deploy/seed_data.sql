-- Seed data for local Docker Compose
-- Note: tables are created by alembic upgrade; this file only inserts sample data
-- after the migration. To use it, run alembic first, then psql -f seed_data.sql

CREATE EXTENSION IF NOT EXISTS btree_gist;

-- Sample hotels (one per country)
INSERT INTO hotels (id, name, country, currency)
VALUES
  ('11111111-1111-1111-1111-111111111111', 'Hotel Bogota Plaza', 'CO', 'COP'),
  ('22222222-2222-2222-2222-222222222222', 'Hotel CDMX Centro',  'MX', 'MXN')
ON CONFLICT DO NOTHING;

-- Sample rooms
INSERT INTO rooms (id, hotel_id, room_type)
VALUES
  ('33333333-3333-3333-3333-333333333333', '11111111-1111-1111-1111-111111111111', 'standard'),
  ('44444444-4444-4444-4444-444444444444', '11111111-1111-1111-1111-111111111111', 'suite'),
  ('55555555-5555-5555-5555-555555555555', '22222222-2222-2222-2222-222222222222', 'standard')
ON CONFLICT DO NOTHING;
