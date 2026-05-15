"""Hotel — referencia al modelo canónico del proyecto.

Inventory NO crea hoteles. Solo consulta `id` y `currency` para heredar moneda
en las tarifas. La tabla canónica `hotel` tiene muchas más columnas (nombre,
direccion, ciudad, etc.) que no se mapean acá porque inventory no las usa.
"""
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Hotel(Base):
    __tablename__ = "hotel"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    habitaciones: Mapped[list["Habitacion"]] = relationship(back_populates="hotel")  # noqa: F821
