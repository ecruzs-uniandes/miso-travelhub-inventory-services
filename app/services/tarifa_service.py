"""Business logic for tarifa management (canonical TravelHub model).

Modelo de promociones (desde 2026-05-14): múltiples tarifas pueden solapar para
la misma habitación — la base (descuento=0) coexiste con promos (descuento>0).
La resolución de cuál aplica para una fecha sigue la regla:

    rango más estrecho gana (más específico), desempate por fechaInicio más reciente.

Ejemplos:
- Base anual + Promo 3 días → la promo gana en sus 3 días
- Base anual + nueva base trimestral (cambio prospectivo) → la trimestral gana
- Subir precio: crear nueva base con rango más estrecho desde la fecha deseada

Enforcement:
- Ownership: hotel_admin solo opera sobre tarifas de habitaciones de su hotel.
- Currency inheritance: tarifa.moneda = habitacion.hotel.currency en creación.
- Kafka events: tarifa_created/tarifa_updated/tarifa_deleted en inventory-rate-events.
- DELETE = hard delete (audit row queda en tarifa_history).
"""
import logging
from datetime import UTC, datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.context import current_hotel_id, current_user_role
from app.exceptions import ForbiddenHotelError, RateNotFoundError
from app.models.habitacion import Habitacion
from app.models.hotel import Hotel
from app.models.tarifa import Tarifa
from app.schemas.tarifa import TarifaCreate, TarifaUpdate

logger = logging.getLogger(__name__)


def _resolution_order():
    """ORDER BY que aplica la regla "rango más estrecho + fechaInicio más reciente"."""
    return [
        (Tarifa.fechaFin - Tarifa.fechaInicio).asc(),
        Tarifa.fechaInicio.desc(),
    ]


class TarifaService:
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

    def _publish(self, event_type: str, tarifa: Tarifa, hotel_id: str) -> None:
        if self._producer is None:
            return
        try:
            from app.services.kafka_producer import publish_tarifa_event
            publish_tarifa_event(
                event_type=event_type,
                hotel_id=hotel_id,
                habitacion_id=tarifa.habitacionId,
                tarifa_id=tarifa.id,
                precio_base=tarifa.precioBase,
                moneda=tarifa.moneda,
                descuento=tarifa.descuento,
                precio_final=tarifa.calcular_precio_final(),
                fecha_inicio=tarifa.fechaInicio.isoformat(),
                fecha_fin=tarifa.fechaFin.isoformat(),
            )
        except Exception as e:
            logger.error(f"Kafka publish failed for {event_type} tarifa {tarifa.id}: {e}")

    async def create(self, data: TarifaCreate) -> Tarifa:
        _, hotel = await self._get_habitacion_with_hotel(data.habitacionId)
        self._check_ownership(hotel.id)
        tarifa = Tarifa(
            habitacionId=data.habitacionId,
            precioBase=data.precioBase,
            moneda=hotel.currency,
            fechaInicio=data.fechaInicio,
            fechaFin=data.fechaFin,
            descuento=data.descuento,
        )
        self.db.add(tarifa)
        await self.db.flush()
        await self.db.refresh(tarifa)
        self._publish("tarifa_created", tarifa, hotel.id)
        return tarifa

    async def get(self, tarifa_id: str) -> Tarifa:
        tarifa = await self.db.get(Tarifa, tarifa_id)
        if tarifa is None:
            raise RateNotFoundError()
        _, hotel = await self._get_habitacion_with_hotel(tarifa.habitacionId)
        self._check_ownership(hotel.id)
        return tarifa

    async def list_by_habitacion(self, habitacion_id: str) -> list[Tarifa]:
        _, hotel = await self._get_habitacion_with_hotel(habitacion_id)
        self._check_ownership(hotel.id)
        stmt = (
            select(Tarifa)
            .where(Tarifa.habitacionId == habitacion_id)
            .order_by(Tarifa.fechaInicio.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_hotel(self, hotel_id: str) -> list[Tarifa]:
        self._check_ownership(hotel_id)
        stmt = (
            select(Tarifa)
            .join(Habitacion, Tarifa.habitacionId == Habitacion.id)
            .where(Habitacion.hotelId == hotel_id)
            .order_by(Tarifa.fechaInicio.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update(self, tarifa_id: str, data: TarifaUpdate) -> Tarifa:
        tarifa = await self.get(tarifa_id)
        _, hotel = await self._get_habitacion_with_hotel(tarifa.habitacionId)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(tarifa, field, value)
        await self.db.flush()
        await self.db.refresh(tarifa)
        self._publish("tarifa_updated", tarifa, hotel.id)
        return tarifa

    async def delete(self, tarifa_id: str) -> None:
        """Hard delete: la canónica no tiene columna `estado`.

        El listener after_flush escribe la fila DELETE en tarifa_history,
        preservando el snapshot final como audit append-only.
        """
        tarifa = await self.get(tarifa_id)
        _, hotel = await self._get_habitacion_with_hotel(tarifa.habitacionId)
        hotel_id = hotel.id
        self._publish("tarifa_deleted", tarifa, hotel_id)
        await self.db.delete(tarifa)
        await self.db.flush()

    async def get_vigente(self, habitacion_id: str, en_fecha: datetime) -> tuple[Tarifa, float]:
        """Tarifa que aplica para `en_fecha` (incluye promos).

        Regla: rango más estrecho gana, desempate por fechaInicio más reciente.
        No tiene check de ownership — lectura pública para search/booking.
        """
        stmt = (
            select(Tarifa)
            .where(
                and_(
                    Tarifa.habitacionId == habitacion_id,
                    Tarifa.fechaInicio <= en_fecha,
                    Tarifa.fechaFin >= en_fecha,
                )
            )
            .order_by(*_resolution_order())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        tarifa = result.scalar_one_or_none()
        if tarifa is None:
            raise RateNotFoundError()
        return tarifa, tarifa.calcular_precio_final()

    async def get_base(
        self, habitacion_id: str, en_fecha: datetime | None = None
    ) -> Tarifa:
        """Tarifa BASE (descuento=0) vigente para `en_fecha` (default now).

        Misma regla de resolución que `/vigente` pero filtrando solo bases.
        Lo consume el front del admin y también el viajero anónimo (público) —
        por eso no hay check de ownership.
        """
        if en_fecha is None:
            en_fecha = datetime.now(UTC)
        stmt = (
            select(Tarifa)
            .where(
                and_(
                    Tarifa.habitacionId == habitacion_id,
                    Tarifa.descuento == 0,
                    Tarifa.fechaInicio <= en_fecha,
                    Tarifa.fechaFin >= en_fecha,
                )
            )
            .order_by(*_resolution_order())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        tarifa = result.scalar_one_or_none()
        if tarifa is None:
            raise RateNotFoundError()
        return tarifa
