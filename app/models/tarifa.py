"""Tarifa — modelo canónico TravelHub.

Esquema EXACTO según DEV (studio_results_20260514_2032.csv):
  id              varchar       NOT NULL
  habitacionId    varchar       NOT NULL  → FK habitacion.id
  precioBase      double prec.  NOT NULL  (> 0)
  moneda          varchar       NOT NULL  (heredada de hotel.currency)
  fechaInicio     timestamptz   NOT NULL
  fechaFin        timestamptz   NOT NULL
  descuento       double prec.  NOT NULL  ([0, 1])

NO existen columnas `estado`/`status`, `created_at`, `updated_at` en la canónica.
- Soft-delete: la tabla no soporta estado → DELETE real. Auditoría queda en `tarifa_history`.
- Timestamps: la auditoría (`tarifa_history.changed_at`) cubre histórico de cambios.
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


def _new_tarifa_id() -> str:
    return str(uuid.uuid4())


class Tarifa(Base):
    __tablename__ = "tarifa"
    __table_args__ = (
        CheckConstraint('"precioBase" > 0', name="ck_tarifa_precio_base_positive"),
        CheckConstraint(
            "descuento >= 0 AND descuento <= 1", name="ck_tarifa_descuento_range"
        ),
        CheckConstraint('"fechaInicio" <= "fechaFin"', name="ck_tarifa_fecha_orden"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_tarifa_id)
    habitacionId: Mapped[str] = mapped_column(
        "habitacionId",
        String,
        ForeignKey("habitacion.id", ondelete="CASCADE"),
        nullable=False,
    )
    precioBase: Mapped[float] = mapped_column("precioBase", Float, nullable=False)
    moneda: Mapped[str] = mapped_column(String, nullable=False)
    fechaInicio: Mapped[datetime] = mapped_column(
        "fechaInicio", DateTime(timezone=True), nullable=False
    )
    fechaFin: Mapped[datetime] = mapped_column(
        "fechaFin", DateTime(timezone=True), nullable=False
    )
    descuento: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    habitacion: Mapped["Habitacion"] = relationship(back_populates="tarifas")  # noqa: F821

    def calcular_precio_final(self) -> float:
        """Domain method: precio_final = precioBase * (1 - descuento)."""
        return round(self.precioBase * (1.0 - self.descuento), 2)
