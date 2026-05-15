"""drop EXCLUDE constraint ex_tarifa_no_overlap — permite múltiples filas para promos

Revision ID: 0004
Create Date: 2026-05-14

Cambio de modelo de negocio: una `habitacion` puede tener múltiples tarifas con
rangos solapados (una base + N promos). El `/vigente` resuelve cuál aplica por
especificidad ("rango más estrecho gana, desempate por fechaInicio más reciente").

Bases (descuento=0) y promos (descuento>0) coexisten en la misma tabla, sin
columna `tipo` adicional — la convención es solo el valor de `descuento`.

Los CheckConstraints (`precioBase>0`, `descuento entre 0 y 1`, `fechaInicio <= fechaFin`)
se mantienen.
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE tarifa DROP CONSTRAINT IF EXISTS ex_tarifa_no_overlap")


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE tarifa
        ADD CONSTRAINT ex_tarifa_no_overlap
        EXCLUDE USING gist (
            "habitacionId" WITH =,
            tstzrange("fechaInicio", "fechaFin", '[]') WITH &&
        )
        """
    )
