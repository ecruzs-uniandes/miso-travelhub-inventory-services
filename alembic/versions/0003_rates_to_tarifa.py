"""drop legacy rates+rate_history; align inventory to canonical tarifa+tarifa_history

Revision ID: 0003
Create Date: 2026-05-14

Esta migración alinea inventory-services al modelo canónico TravelHub:
  - Antes: rates (id UUID, base_price/valid_from/valid_to/discount/status/created_at/updated_at)
  - Después: tarifa (id varchar, precioBase/fechaInicio/fechaFin/descuento, sin estado/timestamps)
  - rate_history → tarifa_history (tarifa_id varchar, FK lógica a tarifa.id)

La tabla `tarifa` YA EXISTE en DEV (esquema canónico creado por search-service / migración previa).
En local docker compose `init-db.sql` la crea desde cero. Esta migración solo:
  1. DROP rate_history (audit legacy)
  2. DROP rates table (todas las rows eran smoke data)
  3. Crea tarifa_history para audit del nuevo modelo
  4. DROP enum rate_status (unused)

NO crea tarifa — esa ya existe en DEV. Para local docker, init-db.sql cubre.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop legacy audit table (será reemplazada por tarifa_history)
    op.execute("DROP INDEX IF EXISTS ix_rate_history_rate_id")
    op.execute("DROP TABLE IF EXISTS rate_history")

    # 2. Drop legacy rates table (canónica usa `tarifa`)
    op.execute("ALTER TABLE IF EXISTS rates DROP CONSTRAINT IF EXISTS ex_rates_no_overlap_active")
    op.execute("DROP INDEX IF EXISTS ix_rates_habitacionId")
    op.execute('DROP INDEX IF EXISTS "ix_rates_habitacionId"')
    op.execute("DROP TABLE IF EXISTS rates")

    # 3. Drop enum rate_status (ya no se usa, la canónica no tiene estado)
    op.execute("DROP TYPE IF EXISTS rate_status")

    # 4. Crear tarifa_history (audit append-only sobre tarifa canónica)
    op.create_table(
        "tarifa_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tarifa_id", sa.String(), nullable=False),
        sa.Column(
            "action",
            postgresql.ENUM("create", "update", "delete", name="audit_action", create_type=False),
            nullable=False,
        ),
        sa.Column("changed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("changed_by_ip", sa.String(45), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("old_values", postgresql.JSONB, nullable=True),
        sa.Column("new_values", postgresql.JSONB, nullable=True),
    )
    op.create_index("ix_tarifa_history_tarifa_id", "tarifa_history", ["tarifa_id"])


def downgrade() -> None:
    """Reversa parcial: recrea rates+rate_history vacíos. La data se perdió en upgrade()."""
    op.drop_index("ix_tarifa_history_tarifa_id", table_name="tarifa_history")
    op.drop_table("tarifa_history")

    rate_status = postgresql.ENUM("active", "inactive", name="rate_status")
    rate_status.create(op.get_bind())

    op.create_table(
        "rates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "habitacionId",
            sa.String(),
            sa.ForeignKey("habitacion.id", ondelete="CASCADE", name="rates_habitacion_fkey"),
            nullable=False,
        ),
        sa.Column("base_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("valid_from", sa.Date, nullable=False),
        sa.Column("valid_to", sa.Date, nullable=False),
        sa.Column("discount", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column(
            "status",
            postgresql.ENUM("active", "inactive", name="rate_status", create_type=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("base_price > 0", name="ck_rate_base_price_positive"),
        sa.CheckConstraint("discount >= 0 AND discount <= 1", name="ck_rate_discount_range"),
        sa.CheckConstraint("valid_from <= valid_to", name="ck_rate_date_order"),
    )
    op.create_index("ix_rates_habitacionId", "rates", ["habitacionId"])

    op.create_table(
        "rate_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("rate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "action",
            postgresql.ENUM("create", "update", "delete", name="audit_action", create_type=False),
            nullable=False,
        ),
        sa.Column("changed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("changed_by_ip", sa.String(45), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("old_values", postgresql.JSONB, nullable=True),
        sa.Column("new_values", postgresql.JSONB, nullable=True),
    )
    op.create_index("ix_rate_history_rate_id", "rate_history", ["rate_id"])
