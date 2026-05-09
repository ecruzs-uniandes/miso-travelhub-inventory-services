"""MFA enforcement.

PF1 mandates MFA for /payments and /admin. For inventory-services rates, MFA
is required only for hotel_admin write operations as a defense-in-depth measure
against compromised hotel credentials. Read endpoints don't require MFA.
"""
from typing import Any

from fastapi import HTTPException, Request, status

from app.middleware.filters.base import AuthFilter

WRITE_METHODS = {"POST", "PATCH", "DELETE"}


class MFAFilter(AuthFilter):
    async def handle(self, request: Request, payload: dict[str, Any]) -> None:
        if request.method in WRITE_METHODS and payload.get("role") == "hotel_admin":
            if not payload.get("mfa_verified"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="MFA required for write operations on rates",
                )
        await self._pass_to_next(request, payload)
