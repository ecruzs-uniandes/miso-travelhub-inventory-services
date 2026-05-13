"""Minimal Hotel entity to support FKs from Room and Rate.

NOTE: Full Hotel CRUD lives in another module of inventory-services.
Here we only need: id, country, currency.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Hotel(Base):
    __tablename__ = "hotels"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)  # ISO 3166-1 alpha-2
    currency: Mapped[str] = mapped_column(String(3), nullable=False)  # ISO 4217
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    rooms: Mapped[list["Room"]] = relationship(back_populates="hotel")  # noqa: F821
