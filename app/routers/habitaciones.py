from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.chain import auth_chain
from app.schemas.habitacion import HabitacionRead
from app.services.habitacion_service import HabitacionService

router = APIRouter(prefix="/api/v1/inventory", tags=["habitaciones"])


@router.get("/hoteles/{hotel_id}/habitaciones")
async def list_habitaciones_by_hotel(
    hotel_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(auth_chain)],
) -> list[HabitacionRead]:
    """Lista las habitaciones de un hotel.

    Para el flujo del admin: ver mis habitaciones → seleccionar una → entrar
    al CRUD de tarifas (`/habitaciones/{id}/tarifas`).

    Auth: hotel_admin solo su hotel, platform_admin cualquier hotel.
    """
    svc = HabitacionService(db)
    habitaciones = await svc.list_by_hotel(hotel_id)
    return [HabitacionRead.model_validate(h) for h in habitaciones]
