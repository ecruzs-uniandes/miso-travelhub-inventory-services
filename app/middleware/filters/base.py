"""Chain of Responsibility — base filter."""
from abc import ABC, abstractmethod
from typing import Any

from fastapi import Request


class AuthFilter(ABC):
    """Abstract base for chain filters. Each filter validates one concern.

    Filters are linked: each one calls `_pass_to_next` after its own check.
    The final handler is reached only when every filter passed.
    """

    def __init__(self) -> None:
        self._next: AuthFilter | None = None

    def set_next(self, nxt: "AuthFilter") -> "AuthFilter":
        self._next = nxt
        return nxt

    async def _pass_to_next(self, request: Request, payload: dict[str, Any]) -> None:
        if self._next is not None:
            await self._next.handle(request, payload)

    @abstractmethod
    async def handle(self, request: Request, payload: dict[str, Any]) -> None: ...
