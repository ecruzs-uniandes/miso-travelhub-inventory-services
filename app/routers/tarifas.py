from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.chain import auth_chain
from app.schemas.tarifa import TarifaCreate, TarifaRead, TarifaUpdate, TarifaVigente
from app.services import kafka_producer as kp
from app.services.tarifa_service import TarifaService

router = APIRouter(prefix="/api/v1/inventory", tags=["tarifas"])


def _svc(db: AsyncSession) -> TarifaService:
    return TarifaService(db, producer=kp.get_producer())


@router.post(
    "/habitaciones/{habitacion_id}/tarifas",
    status_code=status.HTTP_201_CREATED,
    responses={400: {"description": "habitacion_id in path and body must match"}},
)
async def create_tarifa(
    habitacion_id: str,
    body: TarifaCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(auth_chain)],
) -> TarifaRead:
    if body.habitacionId != habitacion_id:
        raise HTTPException(status_code=400, detail="habitacion_id in path and body must match")
    tarifa = await _svc(db).create(body)
    return TarifaRead.model_validate(tarifa)


@router.get("/habitaciones/{habitacion_id}/tarifas")
async def list_tarifas_for_habitacion(
    habitacion_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(auth_chain)],
) -> list[TarifaRead]:
    tarifas = await _svc(db).list_by_habitacion(habitacion_id)
    return [TarifaRead.model_validate(t) for t in tarifas]


@router.get("/habitaciones/{habitacion_id}/tarifas/base")
async def get_tarifa_base(
    habitacion_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(auth_chain)],
    en_fecha: Annotated[datetime | None, Query(alias="fecha")] = None,
) -> TarifaRead:
    """Tarifa BASE (descuento=0) vigente para `fecha` (default now).

    Usado por el front del admin para mostrar la tarifa base actual y editarla.
    Si el admin necesita ver todas las bases (caso multi-base), usa el endpoint
    de listado y filtra por descuento=0.
    """
    tarifa = await _svc(db).get_base(habitacion_id, en_fecha)
    return TarifaRead.model_validate(tarifa)


@router.get("/hoteles/{hotel_id}/tarifas")
async def list_tarifas_for_hotel(
    hotel_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(auth_chain)],
) -> list[TarifaRead]:
    tarifas = await _svc(db).list_by_hotel(hotel_id)
    return [TarifaRead.model_validate(t) for t in tarifas]


# NOTE: /tarifas/vigente must be declared before /tarifas/{tarifa_id}
@router.get("/tarifas/vigente")
async def get_tarifa_vigente(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(auth_chain)],
    habitacion_id: Annotated[str, Query(...)],
    en_fecha: Annotated[datetime, Query(..., alias="fecha")],
) -> TarifaVigente:
    tarifa, final = await _svc(db).get_vigente(habitacion_id, en_fecha)
    return TarifaVigente(
        tarifaId=tarifa.id,
        habitacionId=tarifa.habitacionId,
        precioBase=tarifa.precioBase,
        moneda=tarifa.moneda,
        descuento=tarifa.descuento,
        precioFinal=final,
        fechaInicio=tarifa.fechaInicio,
        fechaFin=tarifa.fechaFin,
    )


@router.get("/tarifas/{tarifa_id}")
async def get_tarifa(
    tarifa_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(auth_chain)],
) -> TarifaRead:
    tarifa = await _svc(db).get(tarifa_id)
    return TarifaRead.model_validate(tarifa)


@router.patch("/tarifas/{tarifa_id}")
async def update_tarifa(
    tarifa_id: str,
    body: TarifaUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(auth_chain)],
) -> TarifaRead:
    tarifa = await _svc(db).update(tarifa_id, body)
    return TarifaRead.model_validate(tarifa)


@router.delete("/tarifas/{tarifa_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tarifa(
    tarifa_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(auth_chain)],
) -> None:
    await _svc(db).delete(tarifa_id)
