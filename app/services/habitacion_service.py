"""Lecturas read-only de habitaciones para el front del admin.

Inventory NO es owner de `habitacion` (lo es search-service), pero como las
tablas viven en la misma BD canonical, expone un listado por hotel como
endpoint complementario al `GET /hoteles/{id}/tarifas` que ya está aquí.

Sin escrituras: la creación/edición/borrado de habitaciones lo hace
search-service / pms.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.context import current_hotel_id, current_user_role
from app.exceptions import ForbiddenHotelError
from app.models.habitacion import Habitacion


class HabitacionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

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

    async def list_by_hotel(self, hotel_id: str) -> list[Habitacion]:
        self._check_ownership(hotel_id)
        stmt = (
            select(Habitacion)
            .where(Habitacion.hotelId == hotel_id)
            .order_by(Habitacion.tipo, Habitacion.id)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
