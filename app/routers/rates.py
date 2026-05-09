from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.chain import auth_chain
from app.schemas.rate import RateCreate, RateEffective, RateRead, RateUpdate
from app.services import kafka_producer as kp
from app.services.rate_service import RateService

router = APIRouter(prefix="/api/v1/inventory", tags=["rates"])


def _svc(db: AsyncSession) -> RateService:
    return RateService(db, producer=kp.get_producer())


@router.post(
    "/rooms/{room_id}/rates",
    status_code=status.HTTP_201_CREATED,
    responses={400: {"description": "room_id in path and body must match"}},
)
async def create_rate(
    room_id: UUID,
    body: RateCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(auth_chain)],
) -> RateRead:
    if body.room_id != room_id:
        raise HTTPException(status_code=400, detail="room_id in path and body must match")
    rate = await _svc(db).create(body)
    return RateRead.model_validate(rate)


@router.get("/rooms/{room_id}/rates")
async def list_rates_for_room(
    room_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(auth_chain)],
) -> list[RateRead]:
    rates = await _svc(db).list_by_room(room_id)
    return [RateRead.model_validate(r) for r in rates]


@router.get("/hotels/{hotel_id}/rates")
async def list_rates_for_hotel(
    hotel_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(auth_chain)],
) -> list[RateRead]:
    rates = await _svc(db).list_by_hotel(hotel_id)
    return [RateRead.model_validate(r) for r in rates]


# NOTE: /rates/effective must be declared before /rates/{rate_id} to avoid
# FastAPI routing /rates/effective as rate_id="effective"
@router.get("/rates/effective")
async def get_effective_rate(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(auth_chain)],
    room_id: Annotated[UUID, Query(...)],
    on_date: Annotated[date, Query(..., alias="date")],
) -> RateEffective:
    rate, final = await _svc(db).get_effective(room_id, on_date)
    return RateEffective(
        rate_id=rate.id,
        room_id=rate.room_id,
        base_price=rate.base_price,
        currency=rate.currency,
        discount=rate.discount,
        final_price=final,
        valid_from=rate.valid_from,
        valid_to=rate.valid_to,
    )


@router.get("/rates/{rate_id}")
async def get_rate(
    rate_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(auth_chain)],
) -> RateRead:
    rate = await _svc(db).get(rate_id)
    return RateRead.model_validate(rate)


@router.patch("/rates/{rate_id}")
async def update_rate(
    rate_id: UUID,
    body: RateUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(auth_chain)],
) -> RateRead:
    rate = await _svc(db).update(rate_id, body)
    return RateRead.model_validate(rate)


@router.delete("/rates/{rate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rate(
    rate_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(auth_chain)],
) -> None:
    await _svc(db).soft_delete(rate_id)
