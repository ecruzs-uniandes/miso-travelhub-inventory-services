"""Context vars to thread request metadata into SQLAlchemy event listeners."""
from contextvars import ContextVar
from uuid import UUID

current_user_id: ContextVar[UUID | None] = ContextVar("current_user_id", default=None)
current_user_role: ContextVar[str | None] = ContextVar("current_user_role", default=None)
current_ip: ContextVar[str | None] = ContextVar("current_ip", default=None)
current_hotel_id: ContextVar[UUID | None] = ContextVar("current_hotel_id", default=None)
