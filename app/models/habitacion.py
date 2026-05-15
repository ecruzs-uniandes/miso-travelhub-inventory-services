"""Habitacion — referencia al modelo canónico del proyecto.

Inventory NO crea habitaciones (eso es de pms/search). Solo las consulta como
FK target. El modelo mapea las 11 columnas de la tabla canónica (todas NOT NULL)
para permitir SELECT, pero solo se exponen las que inventory necesita.
"""
from typing import Any

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Habitacion(Base):
    __tablename__ = "habitacion"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    # Nota: la columna BD es "hotelId" (camelCase). SQLAlchemy preserva el nombre
    # del Python attribute como nombre de columna por default, pero acá lo forzamos.
    hotelId: Mapped[str] = mapped_column(
        "hotelId", String, ForeignKey("hotel.id", ondelete="CASCADE"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(String, nullable=False)
    categoria: Mapped[str] = mapped_column(String, nullable=False)
    capacidadMaxima: Mapped[int] = mapped_column("capacidadMaxima", Integer, nullable=False)
    descripcion: Mapped[str] = mapped_column(String, nullable=False)
    imagenes: Mapped[Any] = mapped_column(JSON, nullable=False)
    tipo_habitacion: Mapped[str] = mapped_column(String, nullable=False)
    tipo_cama: Mapped[Any] = mapped_column(JSON, nullable=False)
    tamano_habitacion: Mapped[str] = mapped_column(String, nullable=False)
    amenidades: Mapped[Any] = mapped_column(JSON, nullable=False)

    hotel: Mapped["Hotel"] = relationship(back_populates="habitaciones")  # noqa: F821
    tarifas: Mapped[list["Tarifa"]] = relationship(back_populates="habitacion")  # noqa: F821
