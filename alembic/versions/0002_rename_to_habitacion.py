"""rename Room→Habitacion, switch rates FK from rooms.id (UUID) to habitacion.id (varchar)

Revision ID: 0002
Create Date: 2026-05-14

Esta migración alinea inventory-services al modelo canónico:
  - Antes: rates.room_id (UUID) → rooms.id (UUID)
  - Después: rates.habitacionId (varchar) → habitacion.id (varchar)

La tabla `habitacion` ya existe en BD (creada por search-service / pms canonical).
La tabla `rooms` (UUID) queda en BD pero inventory ya no la usa — drop diferido al
sprint de cleanup cuando pms-integration y pms-sync-worker también estén migrados.

Data preservation:
  - DELETE rates + rate_history existentes. Solo había 1 row del smoke E2E
    apuntando a rooms.id que no tiene equivalente en habitacion.id.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Limpiar rate_history y rates (rows actuales apuntan a rooms.id, no migrables).
    op.execute("DELETE FROM rate_history")
    op.execute("DELETE FROM rates")

    # 2. Drop el EXCLUDE constraint que referencia room_id
    op.execute("ALTER TABLE rates DROP CONSTRAINT IF EXISTS ex_rates_no_overlap_active")

    # 3. Drop el FK + index sobre room_id
    op.execute(
        "ALTER TABLE rates DROP CONSTRAINT IF EXISTS rates_room_id_fkey"
    )
    op.execute("DROP INDEX IF EXISTS ix_rates_room_id")

    # 4. Rename column room_id → habitacionId con cambio de type UUID → VARCHAR.
    #    Como ya borramos data y el FK, usamos drop + add para evitar cast.
    op.drop_column("rates", "room_id")
    op.add_column(
        "rates",
        sa.Column(
            "habitacionId",
            sa.String(),
            sa.ForeignKey("habitacion.id", ondelete="CASCADE", name="rates_habitacion_fkey"),
            nullable=False,
        ),
    )
    op.create_index("ix_rates_habitacionId", "rates", ["habitacionId"])

    # 5. Re-crear EXCLUDE constraint sobre el nuevo campo
    op.execute(
        """
        ALTER TABLE rates
        ADD CONSTRAINT ex_rates_no_overlap_active
        EXCLUDE USING gist (
            "habitacionId" WITH =,
            daterange(valid_from, valid_to, '[]') WITH &&
        ) WHERE (status = 'active')
        """
    )


def downgrade() -> None:
    # Reverse: vuelve a room_id (UUID) FK a rooms.id
    op.execute("DELETE FROM rate_history")
    op.execute("DELETE FROM rates")
    op.execute("ALTER TABLE rates DROP CONSTRAINT IF EXISTS ex_rates_no_overlap_active")
    op.drop_index("ix_rates_habitacionId", table_name="rates")
    op.drop_column("rates", "habitacionId")
    op.add_column(
        "rates",
        sa.Column(
            "room_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("rooms.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    op.create_index("ix_rates_room_id", "rates", ["room_id"])
    op.execute(
        """
        ALTER TABLE rates
        ADD CONSTRAINT ex_rates_no_overlap_active
        EXCLUDE USING gist (
            room_id WITH =,
            daterange(valid_from, valid_to, '[]') WITH &&
        ) WHERE (status = 'active')
        """
    )
