from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.rate import RateStatus


class RateCreate(BaseModel):
    habitacionId: str
    base_price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    valid_from: date
    valid_to: date
    discount: Decimal = Field(default=Decimal("0"), ge=0, le=1, max_digits=5, decimal_places=4)

    @model_validator(mode="after")
    def _check_dates(self) -> "RateCreate":
        if self.valid_from > self.valid_to:
            raise ValueError("valid_from must be <= valid_to")
        return self


class RateUpdate(BaseModel):
    base_price: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    valid_from: date | None = None
    valid_to: date | None = None
    discount: Decimal | None = Field(default=None, ge=0, le=1, max_digits=5, decimal_places=4)
    status: RateStatus | None = None


class RateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    habitacionId: str
    base_price: Decimal
    currency: str
    valid_from: date
    valid_to: date
    discount: Decimal
    status: RateStatus
    created_at: datetime
    updated_at: datetime


class RateEffective(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rate_id: UUID
    habitacionId: str
    base_price: Decimal
    currency: str
    discount: Decimal
    final_price: Decimal
    valid_from: date
    valid_to: date
