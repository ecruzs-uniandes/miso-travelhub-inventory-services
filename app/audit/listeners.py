"""SQLAlchemy event listeners that mirror Tarifa changes into tarifa_history.

Uses contextvars (current_user_id, current_ip) populated by the auth chain.
"""
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.context import current_ip, current_user_id
from app.models.tarifa import Tarifa
from app.models.tarifa_history import AuditAction, TarifaHistory


def _serialize(tarifa: Tarifa) -> dict:
    def conv(v):
        if isinstance(v, date | datetime):
            return v.isoformat()
        if isinstance(v, UUID):
            return str(v)
        if hasattr(v, "value"):  # enum
            return v.value
        return v

    return {
        "id": tarifa.id,
        "habitacionId": tarifa.habitacionId,
        "precioBase": tarifa.precioBase,
        "moneda": tarifa.moneda,
        "fechaInicio": conv(tarifa.fechaInicio),
        "fechaFin": conv(tarifa.fechaFin),
        "descuento": tarifa.descuento,
    }


_listeners_registered = False


def register_tarifa_audit_listeners() -> None:
    global _listeners_registered
    if _listeners_registered:
        return
    _listeners_registered = True

    @event.listens_for(Session, "after_flush")
    def _after_flush(session: Session, flush_context):
        for obj in session.new:
            if isinstance(obj, Tarifa):
                session.add(
                    TarifaHistory(
                        tarifa_id=obj.id,
                        action=AuditAction.CREATE,
                        changed_by_user_id=current_user_id.get(),
                        changed_by_ip=current_ip.get(),
                        old_values=None,
                        new_values=_serialize(obj),
                    )
                )
        for obj in session.dirty:
            if isinstance(obj, Tarifa) and session.is_modified(obj):
                hist_old = {}
                from sqlalchemy import inspect

                state = inspect(obj)
                for attr in state.attrs:
                    h = attr.load_history()
                    if h.has_changes():
                        hist_old[attr.key] = h.deleted[0] if h.deleted else None
                session.add(
                    TarifaHistory(
                        tarifa_id=obj.id,
                        action=AuditAction.UPDATE,
                        changed_by_user_id=current_user_id.get(),
                        changed_by_ip=current_ip.get(),
                        old_values={k: str(v) for k, v in hist_old.items()},
                        new_values=_serialize(obj),
                    )
                )
        for obj in session.deleted:
            if isinstance(obj, Tarifa):
                session.add(
                    TarifaHistory(
                        tarifa_id=obj.id,
                        action=AuditAction.DELETE,
                        changed_by_user_id=current_user_id.get(),
                        changed_by_ip=current_ip.get(),
                        old_values=_serialize(obj),
                        new_values=None,
                    )
                )
