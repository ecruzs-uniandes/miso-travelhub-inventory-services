"""Validates the request IP is consistent with the JWT 'country' claim.

PF1 placeholder: real geolocation requires MaxMind GeoIP or Cloud Armor enrichment.
For MVP we just store the IP into context for audit. The full check is a TODO.
"""
from typing import Any

from fastapi import Request

from app.context import current_ip
from app.middleware.filters.base import AuthFilter


class IPValidationFilter(AuthFilter):
    async def handle(self, request: Request, payload: dict[str, Any]) -> None:
        # Trust X-Forwarded-For from the LB; fall back to client.host
        forwarded = request.headers.get("x-forwarded-for")
        ip = forwarded.split(",")[0].strip() if forwarded else (
            request.client.host if request.client else "unknown"
        )
        current_ip.set(ip)
        # TODO: validate ip-country consistency against payload['country']
        await self._pass_to_next(request, payload)
