"""Decodes JWT WITHOUT verifying signature.

The API Gateway has already validated:
- RS256 signature (via JWKS endpoint)
- Issuer claim
- Audience claim
- Expiration

The backend only needs to read claims for RBAC, MFA, and audit purposes.
"""
from typing import Any

from fastapi import Request
from jose import jwt

from app.config import settings
from app.exceptions import InvalidJWTError


def decode_jwt(token: str) -> dict[str, Any]:
    try:
        payload = jwt.get_unverified_claims(token)
    except Exception as e:
        raise InvalidJWTError(f"Cannot decode JWT: {e}") from e

    if payload.get("iss") != settings.jwt_issuer:
        raise InvalidJWTError("Invalid issuer")

    # aud can be a string or list depending on the issuer
    aud = payload.get("aud")
    if isinstance(aud, list):
        if settings.jwt_audience not in aud:
            raise InvalidJWTError("Invalid audience")
    elif aud != settings.jwt_audience:
        raise InvalidJWTError("Invalid audience")

    if not payload.get("sub"):
        raise InvalidJWTError("Missing subject")
    if not payload.get("role"):
        raise InvalidJWTError("Missing role")

    return payload


def extract_token(request: Request) -> str:
    # API Gateway replaces Authorization with its own OIDC token and moves the
    # user JWT to X-Forwarded-Authorization. Check that header first.
    for header in ("x-forwarded-authorization", "authorization"):
        value = request.headers.get(header, "")
        if value.lower().startswith("bearer "):
            return value[7:]
    raise InvalidJWTError("Missing Authorization header")
