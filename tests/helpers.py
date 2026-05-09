"""Helpers for generating test JWTs (signature is not validated by the backend)."""
import time
from uuid import UUID, uuid4

from jose import jwt

from app.config import settings


def make_token(
    user_id: UUID | None = None,
    role: str = "hotel_admin",
    hotel_id: UUID | None = None,
    mfa_verified: bool = True,
    country: str = "CO",
) -> str:
    payload = {
        "sub": str(user_id or uuid4()),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "exp": int(time.time()) + 900,
        "iat": int(time.time()),
        "role": role,
        "mfa_verified": mfa_verified,
        "country": country,
        "hotel_id": str(hotel_id) if hotel_id else None,
    }
    # Any secret works; the backend never verifies the signature
    return jwt.encode(payload, "test-secret", algorithm="HS256")


def auth_headers(**kwargs) -> dict:
    return {"Authorization": f"Bearer {make_token(**kwargs)}"}
