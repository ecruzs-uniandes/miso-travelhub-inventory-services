"""Wires the Chain of Responsibility and exposes it as a FastAPI dependency."""
from fastapi import Request

from app.auth.jwt_decoder import decode_jwt, extract_token
from app.middleware.filters.ip_validation import IPValidationFilter
from app.middleware.filters.rate_limit import RateLimitFilter
from app.middleware.filters.rbac import RBACFilter


def _build_chain() -> RateLimitFilter:
    rate_limit = RateLimitFilter()
    ip_validation = IPValidationFilter()
    rbac = RBACFilter()
    rate_limit.set_next(ip_validation).set_next(rbac)
    return rate_limit


_CHAIN = _build_chain()


async def auth_chain(request: Request) -> dict:
    token = extract_token(request)
    payload = decode_jwt(token)
    await _CHAIN.handle(request, payload)
    return payload
