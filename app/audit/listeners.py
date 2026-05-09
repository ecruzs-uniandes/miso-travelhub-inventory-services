"""SQLAlchemy event listeners that mirror Rate changes into rate_history.

Uses contextvars (current_user_id, current_ip) populated by the auth chain.
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.context import current_ip, current_user_id
from app.models.rate import Rate
from app.models.rate_history import AuditAction, RateHistory


def _serialize(rate: Rate) -> dict:
    def conv(v):
        if isinstance(v, Decimal):
            return str(v)
        if isinstance(v, (date, datetime)):
            return v.isoformat()
        if isinstance(v, UUID):
            return str(v)
        if hasattr(v, "value"):  # enum
            return v.value
        return v

    return {
        "id": conv(rate.id),
        "room_id": conv(rate.room_id),
        "base_price": conv(rate.base_price),
        "currency": rate.currency,
        "valid_from": conv(rate.valid_from),
        "valid_to": conv(rate.valid_to),
        "discount": conv(rate.discount),
        "status": conv(rate.status),
    }


def register_rate_audit_listeners() -> None:
    @event.listens_for(Session, "after_flush")
    def _after_flush(session: Session, flush_context):
        for obj in session.new:
            if isinstance(obj, Rate):
                session.add(
                    RateHistory(
                        rate_id=obj.id,
                        action=AuditAction.CREATE,
                        changed_by_user_id=current_user_id.get(),
                        changed_by_ip=current_ip.get(),
                        old_values=None,
                        new_values=_serialize(obj),
                    )
                )
        for obj in session.dirty:
            if isinstance(obj, Rate) and session.is_modified(obj):
                # Get old values from history attribute
                hist_old = {}
                from sqlalchemy import inspect

                state = inspect(obj)
                for attr in state.attrs:
                    h = attr.load_history()
                    if h.has_changes():
                        hist_old[attr.key] = h.deleted[0] if h.deleted else None
                session.add(
                    RateHistory(
                        rate_id=obj.id,
                        action=AuditAction.UPDATE,
                        changed_by_user_id=current_user_id.get(),
                        changed_by_ip=current_ip.get(),
                        old_values={k: str(v) for k, v in hist_old.items()},
                        new_values=_serialize(obj),
                    )
                )
        for obj in session.deleted:
            if isinstance(obj, Rate):
                session.add(
                    RateHistory(
                        rate_id=obj.id,
                        action=AuditAction.DELETE,
                        changed_by_user_id=current_user_id.get(),
                        changed_by_ip=current_ip.get(),
                        old_values=_serialize(obj),
                        new_values=None,
                    )
                )
