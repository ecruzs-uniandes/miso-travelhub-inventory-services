"""Business logic for rate management.

Enforces:
- Ownership: hotel_admin can only operate on rates of habitaciones in own hotel
- No-overlap: no two ACTIVE rates on the same habitacion can have overlapping date ranges
- Currency inheritance: rate.currency = habitacion.hotel.currency (set at creation)
- Kafka events: publishes rate_created/rate_updated/rate_deactivated to inventory-rate-events
"""
import logging
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.context import current_hotel_id, current_user_role
from app.exceptions import ForbiddenHotelError, RateNotFoundError, RateOverlapError
from app.models.habitacion import Habitacion
from app.models.hotel import Hotel
from app.models.rate import Rate, RateStatus
from app.schemas.rate import RateCreate, RateUpdate

logger = logging.getLogger(__name__)


class RateService:
    def __init__(self, db: AsyncSession, producer=None) -> None:
        self.db = db
        self._producer = producer

    async def _get_habitacion_with_hotel(self, habitacion_id: str) -> tuple[Habitacion, Hotel]:
        stmt = (
            select(Habitacion, Hotel)
            .join(Hotel, Habitacion.hotelId == Hotel.id)
            .where(Habitacion.id == habitacion_id)
        )
        result = await self.db.execute(stmt)
        row = result.first()
        if row is None:
            raise RateNotFoundError()
        return row[0], row[1]

    def _check_ownership(self, hotel_id: str) -> None:
        role = current_user_role.get()
        if role == "platform_admin":
            return
        if role == "hotel_admin":
            ctx_hotel = current_hotel_id.get()
            ctx_str = str(ctx_hotel) if ctx_hotel else None
            if ctx_str != hotel_id:
                raise ForbiddenHotelError()
            return
        raise ForbiddenHotelError()

    async def _assert_no_overlap(
        self,
        habitacion_id: str,
        valid_from: date,
        valid_to: date,
        exclude_rate_id: UUID | None = None,
    ) -> None:
        # Two ranges overlap iff: A.from <= B.to AND B.from <= A.to
        conditions = [
            Rate.habitacionId == habitacion_id,
            Rate.status == RateStatus.ACTIVE,
            Rate.valid_from <= valid_to,
            valid_from <= Rate.valid_to,
        ]
        if exclude_rate_id is not None:
            conditions.append(Rate.id != exclude_rate_id)
        stmt = select(Rate.id).where(and_(*conditions)).limit(1)
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none() is not None:
            raise RateOverlapError(
                f"An active rate already covers part of {valid_from}..{valid_to} for this habitacion"
            )

    def _publish(self, event_type: str, rate: Rate, hotel_id: str) -> None:
        if self._producer is None:
            return
        try:
            from app.services.kafka_producer import publish_rate_event
            publish_rate_event(
                event_type=event_type,
                hotel_id=hotel_id,
                room_id=rate.habitacionId,
                rate_id=rate.id,
                base_price=rate.base_price,
                currency=rate.currency,
                discount=rate.discount,
                final_price=rate.calcular_precio_final(),
                valid_from=rate.valid_from.isoformat(),
                valid_to=rate.valid_to.isoformat(),
                status=rate.status.value,
            )
        except Exception as e:
            logger.error(f"Kafka publish failed for {event_type} rate {rate.id}: {e}")

    async def create(self, data: RateCreate) -> Rate:
        _, hotel = await self._get_habitacion_with_hotel(data.habitacionId)
        self._check_ownership(hotel.id)
        await self._assert_no_overlap(data.habitacionId, data.valid_from, data.valid_to)
        rate = Rate(
            habitacionId=data.habitacionId,
            base_price=data.base_price,
            currency=hotel.currency,
            valid_from=data.valid_from,
            valid_to=data.valid_to,
            discount=data.discount,
            status=RateStatus.ACTIVE,
        )
        self.db.add(rate)
        await self.db.flush()
        await self.db.refresh(rate)
        self._publish("rate_created", rate, hotel.id)
        return rate

    async def get(self, rate_id: UUID) -> Rate:
        rate = await self.db.get(Rate, rate_id)
        if rate is None:
            raise RateNotFoundError()
        _, hotel = await self._get_habitacion_with_hotel(rate.habitacionId)
        self._check_ownership(hotel.id)
        return rate

    async def list_by_habitacion(self, habitacion_id: str) -> list[Rate]:
        _, hotel = await self._get_habitacion_with_hotel(habitacion_id)
        self._check_ownership(hotel.id)
        stmt = select(Rate).where(Rate.habitacionId == habitacion_id).order_by(Rate.valid_from.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_hotel(self, hotel_id: str) -> list[Rate]:
        self._check_ownership(hotel_id)
        stmt = (
            select(Rate)
            .join(Habitacion, Rate.habitacionId == Habitacion.id)
            .where(Habitacion.hotelId == hotel_id)
            .order_by(Rate.valid_from.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update(self, rate_id: UUID, data: RateUpdate) -> Rate:
        rate = await self.get(rate_id)
        _, hotel = await self._get_habitacion_with_hotel(rate.habitacionId)
        new_from = data.valid_from or rate.valid_from
        new_to = data.valid_to or rate.valid_to
        new_status = data.status or rate.status
        if new_status == RateStatus.ACTIVE:
            await self._assert_no_overlap(
                rate.habitacionId, new_from, new_to, exclude_rate_id=rate.id
            )
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(rate, field, value)
        await self.db.flush()
        await self.db.refresh(rate)
        self._publish("rate_updated", rate, hotel.id)
        return rate

    async def soft_delete(self, rate_id: UUID) -> None:
        rate = await self.get(rate_id)
        _, hotel = await self._get_habitacion_with_hotel(rate.habitacionId)
        rate.status = RateStatus.INACTIVE
        await self.db.flush()
        self._publish("rate_deactivated", rate, hotel.id)

    async def get_effective(self, habitacion_id: str, on_date: date) -> tuple[Rate, Decimal]:
        """Public read for search/booking — no RBAC ownership check."""
        stmt = select(Rate).where(
            and_(
                Rate.habitacionId == habitacion_id,
                Rate.status == RateStatus.ACTIVE,
                Rate.valid_from <= on_date,
                Rate.valid_to >= on_date,
            )
        )
        result = await self.db.execute(stmt)
        rate = result.scalar_one_or_none()
        if rate is None:
            raise RateNotFoundError()
        return rate, rate.calcular_precio_final()
