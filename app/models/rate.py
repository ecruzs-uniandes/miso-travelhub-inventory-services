import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class RateStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class Rate(Base):
    __tablename__ = "rates"
    __table_args__ = (
        CheckConstraint("base_price > 0", name="ck_rate_base_price_positive"),
        CheckConstraint(
            "discount >= 0 AND discount <= 1", name="ck_rate_discount_range"
        ),
        CheckConstraint("valid_from <= valid_to", name="ck_rate_date_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False
    )
    base_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date] = mapped_column(Date, nullable=False)
    discount: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, default=Decimal("0")
    )
    status: Mapped[RateStatus] = mapped_column(
        Enum(RateStatus, name="rate_status"),
        nullable=False,
        default=RateStatus.ACTIVE,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    room: Mapped["Room"] = relationship(back_populates="rates")  # noqa: F821

    def calcular_precio_final(self) -> Decimal:
        """Domain method per PF1 model: precio_final = base_price * (1 - discount)."""
        return (self.base_price * (Decimal("1") - self.discount)).quantize(Decimal("0.01"))
