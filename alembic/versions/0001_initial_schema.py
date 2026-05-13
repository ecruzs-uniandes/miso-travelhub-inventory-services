"""initial schema with hotels, rooms, rates, rate_history + exclude constraint

Revision ID: 0001
Create Date: 2026-05-09

DB compartida con search/booking que ya pueden tener creadas las tablas
hotels y rooms. Si existen las saltamos, si no las creamos.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _existing_tables() -> set[str]:
    bind = op.get_bind()
    return set(sa.inspect(bind).get_table_names())


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    existing = _existing_tables()

    if "hotels" not in existing:
        op.create_table(
            "hotels",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("country", sa.String(2), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if "rooms" not in existing:
        op.create_table(
            "rooms",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "hotel_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("hotels.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("room_type", sa.String(50), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_rooms_hotel_id", "rooms", ["hotel_id"])

    # rate_status enum: crear si no existe
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE rate_status AS ENUM ('active', 'inactive'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )

    if "rates" not in existing:
        op.create_table(
            "rates",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "room_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("rooms.id", ondelete="CASCADE"),
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

    # audit_action enum: crear si no existe
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE audit_action AS ENUM ('create', 'update', 'delete'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )

    if "rate_history" not in existing:
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


def downgrade() -> None:
    # Solo dropea lo propio de inventory; hotels/rooms pueden ser de otros servicios
    op.drop_index("ix_rate_history_rate_id", table_name="rate_history")
    op.drop_table("rate_history")
    op.execute("DROP TYPE IF EXISTS audit_action")
    op.execute("ALTER TABLE rates DROP CONSTRAINT IF EXISTS ex_rates_no_overlap_active")
    op.drop_index("ix_rates_room_id", table_name="rates")
    op.drop_table("rates")
    op.execute("DROP TYPE IF EXISTS rate_status")
