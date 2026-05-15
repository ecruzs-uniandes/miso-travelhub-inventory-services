"""RBAC: validates the role against the requested route.

For inventory-services tarifa module:
- traveler:        FORBIDDEN
- hotel_admin:     allowed only for tarifas de habitaciones de su hotel
                   (the per-resource hotel_id check happens in the service layer)
- platform_admin:  allowed for everything

Fine-grained ownership is enforced in the service layer (see TarifaService).
"""
from typing import Any

from fastapi import HTTPException, Request, status

from app.context import current_hotel_id, current_user_id, current_user_role
from app.middleware.filters.base import AuthFilter

ALLOWED_ROLES = {"hotel_admin", "platform_admin"}


class RBACFilter(AuthFilter):
    async def handle(self, request: Request, payload: dict[str, Any]) -> None:
        role = payload.get("role")
        if role not in ALLOWED_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' cannot access inventory tarifas",
            )

        # Populate context for downstream service-layer checks and audit
        from uuid import UUID

        sub = payload.get("sub")
        hotel = payload.get("hotel_id")
        current_user_id.set(UUID(sub) if sub else None)
        current_user_role.set(role)
        current_hotel_id.set(UUID(hotel) if hotel else None)

        await self._pass_to_next(request, payload)
